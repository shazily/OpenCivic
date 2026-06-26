"""S3/Minio blob storage connector — event-triggered or scheduled pull."""
import uuid
from datetime import datetime
from typing import Any, AsyncIterator

import structlog

from connectors.base.connector_base import ConnectorBase, ConnectionTestResult, RecordBatch, SchemaSnapshot

logger = structlog.get_logger(__name__)


class S3Connector(ConnectorBase):
    """
    Reads CSV/Parquet/JSON files from S3 or Minio.
    Prefix-aware: scans a folder prefix and ingests all matching files.
    Incremental: uses LastModified metadata to only pull new/changed files.
    """
    CONNECTOR_TYPE = "s3"

    def _client(self):
        import boto3
        return boto3.client(
            "s3",
            endpoint_url=self._config.get("endpoint_url"),  # Minio: http://minio:9000
            aws_access_key_id=self._config["access_key"],
            aws_secret_access_key=self._config["secret_key"],
            region_name=self._config.get("region", "us-east-1"),
        )

    async def test_connection(self) -> ConnectionTestResult:
        import asyncio, time
        try:
            start = time.monotonic()
            loop = asyncio.get_event_loop()
            def check():
                client = self._client()
                client.head_bucket(Bucket=self._config["bucket"])
            await loop.run_in_executor(None, check)
            return ConnectionTestResult(success=True, message="OK", latency_ms=int((time.monotonic() - start) * 1000))
        except Exception as e:
            return ConnectionTestResult(success=False, message=str(e))

    async def get_schema(self) -> SchemaSnapshot:
        # Schema inferred from first file in prefix
        return SchemaSnapshot(columns=[], row_count=None, sampled_at=datetime.utcnow())

    async def pull(self, since: datetime | None = None) -> AsyncIterator[RecordBatch]:
        import asyncio
        import pandas as pd
        import pyarrow.parquet as pq
        import io

        loop = asyncio.get_event_loop()
        bucket = self._config["bucket"]
        prefix = self._config.get("prefix", "")
        batch_size = self._config.get("batch_size", 1000)

        def list_objects():
            client = self._client()
            paginator = client.get_paginator("list_objects_v2")
            files = []
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    if since is None or obj["LastModified"].replace(tzinfo=None) > since:
                        files.append(obj["Key"])
            return files

        keys = await loop.run_in_executor(None, list_objects)
        batch_num = 0
        for key in keys:
            def read_file(k=key):
                client = self._client()
                obj = client.get_object(Bucket=bucket, Key=k)
                data = obj["Body"].read()
                if k.endswith(".parquet"):
                    return pq.read_table(io.BytesIO(data)).to_pydict()
                elif k.endswith(".csv"):
                    df = pd.read_csv(io.BytesIO(data))
                    return df.to_dict(orient="records")
                elif k.endswith(".json"):
                    import json
                    return json.loads(data)
                return []
            records = await loop.run_in_executor(None, read_file)
            if isinstance(records, dict):
                # Parquet returns column-oriented dict — convert to rows
                cols = list(records.keys())
                records = [dict(zip(cols, vals)) for vals in zip(*records.values())]
            for i in range(0, len(records), batch_size):
                batch_num += 1
                yield RecordBatch(records=records[i:i + batch_size], batch_number=batch_num, total_batches=None)

    async def close(self) -> None:
        pass
