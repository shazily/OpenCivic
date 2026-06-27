"""Convert inferred DataFrames to Parquet bytes for object storage."""

import io
import uuid

import pyarrow as pa
import pyarrow.parquet as pq


def parquet_storage_key(tenant_id: uuid.UUID, dataset_id: uuid.UUID, version_number: int) -> str:
    """Object storage key for a dataset version Parquet snapshot."""
    return f"parquet/{tenant_id}/{dataset_id}/v{version_number}.parquet"


def dataframe_to_parquet_bytes(dataframe: object) -> bytes:
    """Serialize a pandas DataFrame to Parquet columnar format."""
    table = pa.Table.from_pandas(dataframe, preserve_index=False)
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()
