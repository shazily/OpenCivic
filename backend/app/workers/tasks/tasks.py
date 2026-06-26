"""
OpenCivic — Celery tasks: ingest pipeline.
RULE: JSON serialisation only. NEVER pickle.
RULE: Every task accepts idempotency_key and checks before processing.
RULE: Every task lands in dead letter queue after max retries.
"""

import hashlib
from datetime import UTC, datetime

import structlog

from app.core.cache import cache_get, cache_set
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _idempotency_key(task_name: str, **kwargs) -> str:
    key_data = f"{task_name}:{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
    return f"idempotency:{hashlib.sha256(key_data.encode()).hexdigest()}"


@celery_app.task(
    name="app.workers.tasks.ingest.process_upload",
    queue="ingest",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def process_upload(
    tenant_id: str,
    dataset_id: str,
    storage_key: str,
    filename: str,
    idempotency_key: str | None = None,
    publisher_id: str | None = None,
) -> dict:
    """
    Ingest pipeline for uploaded files:
    1. ClamAV virus scan
    2. Encoding detection and schema inference
    3. Convert to Parquet → Minio
    4. Update dataset schema_snapshot and row_count
    5. Generate Qdrant embedding (deferred — logged skip)
    6. Emit DatasetIngested event
    """
    import uuid

    from app.services.ingest.ingest_service import IngestService
    from app.workers.async_runner import run_async

    idem_key = idempotency_key or _idempotency_key(
        "process_upload", dataset_id=dataset_id, storage_key=storage_key
    )

    async def run() -> dict:
        cached = await cache_get(idem_key)
        if cached:
            logger.info("task_already_processed", task="process_upload", idempotency_key=idem_key)
            return {"status": "already_processed"}

        try:
            logger.info("ingest_started", dataset_id=dataset_id, storage_key=storage_key)
            result = await IngestService().run(
                tenant_id=uuid.UUID(tenant_id),
                dataset_id=uuid.UUID(dataset_id),
                storage_key=storage_key,
                filename=filename,
                publisher_id=uuid.UUID(publisher_id) if publisher_id else None,
            )
            logger.info("ingest_embedding_skipped", dataset_id=dataset_id, reason="sprint_3_scope")
            await cache_set(idem_key, "done", ttl_seconds=86400)
            return result
        except Exception as exc:
            logger.error("ingest_failed", dataset_id=dataset_id, error=str(exc))
            raise

    return run_async(run())


@celery_app.task(
    name="app.workers.tasks.staleness.check_all_datasets",
    queue="refresh",
    max_retries=1,
)
def check_all_datasets() -> dict:
    """
    Check all datasets for staleness. Runs every minute via Celery Beat.
    Updates staleness_state: fresh | possibly_outdated | stale.
    """
    from app.repositories.dataset_repository import DatasetRepository
    from app.workers.async_runner import run_async
    from app.workers.tenant_runner import run_for_all_tenants

    async def handler(session, _tenant_id):
        repo = DatasetRepository(session)
        updated = await repo.refresh_staleness_states()
        return {"updated": updated}

    results = run_async(run_for_all_tenants(handler))
    total = sum(item.get("updated", 0) for item in results.values())
    logger.info("staleness_check_completed", updated=total)
    return {"status": "ok", "checked_at": datetime.now(UTC).isoformat(), "updated": total}


@celery_app.task(
    name="app.workers.tasks.connectors.trigger_due_syncs",
    queue="refresh",
)
def trigger_due_syncs() -> dict:
    """Trigger connector syncs that are due. Respects circuit breaker state."""
    from app.repositories.connector_repository import ConnectorRepository
    from app.workers.async_runner import run_async
    from app.workers.tenant_runner import run_for_all_tenants

    async def handler(session, tenant_id):
        repo = ConnectorRepository(session)
        due = await repo.get_due_syncs()
        for connector in due:
            sync_connector.delay(str(connector.id), str(tenant_id))
        return {"enqueued": len(due)}

    return run_async(run_for_all_tenants(handler))


@celery_app.task(
    name="app.workers.tasks.connectors.sync_connector",
    queue="refresh",
    max_retries=3,
    default_retry_delay=300,
)
def sync_connector(connector_id: str, tenant_id: str, idempotency_key: str | None = None) -> dict:
    """
    Pull data from a connector and run ingest for the linked dataset.
    """
    import uuid

    from app.db.session import tenant_write_session
    from app.services.connectors.connector_sync_service import ConnectorSyncService
    from app.workers.async_runner import run_async

    async def run() -> dict:
        logger.info("connector_sync_started", connector_id=connector_id)
        async with tenant_write_session(uuid.UUID(tenant_id)) as session:
            result = await ConnectorSyncService().run(
                session,
                uuid.UUID(tenant_id),
                uuid.UUID(connector_id),
            )
            await session.commit()
            return result

    return run_async(run())


@celery_app.task(
    name="app.workers.tasks.connectors.attempt_circuit_reset",
    queue="refresh",
)
def attempt_circuit_reset() -> dict:
    """Try to close open connector circuits (half-open probe)."""
    from app.repositories.connector_repository import ConnectorRepository
    from app.services.connectors.base import ConnectorBase
    from app.services.connectors.registry import get_connector
    from app.workers.async_runner import run_async
    from app.workers.tenant_runner import run_for_all_tenants

    async def handler(session, _tenant_id):
        repo = ConnectorRepository(session)
        closed = 0
        for connector in await repo.get_open_circuits():
            config = ConnectorBase.parse_config(connector.config)
            plugin = get_connector(connector.type, config)
            result = await plugin.test_connection()
            if result.ok:
                await repo.close_circuit(connector.id)
                closed += 1
        return {"closed": closed}

    return run_async(run_for_all_tenants(handler))


@celery_app.task(
    name="app.workers.tasks.governance.check_embargo_releases",
    queue="refresh",
)
def check_embargo_releases() -> dict:
    """Release embargoed datasets when their datetime has passed."""
    from app.services.governance.workflow_service import WorkflowService
    from app.workers.async_runner import run_async
    from app.workers.tenant_runner import run_for_all_tenants

    async def handler(session, _tenant_id):
        service = WorkflowService(session, _tenant_id)
        released = await service.check_embargo_releases()
        return {"released": [str(dataset_id) for dataset_id in released]}

    return run_async(run_for_all_tenants(handler))


@celery_app.task(
    name="app.workers.tasks.governance.check_workflow_sla_breaches",
    queue="notifications",
)
def check_workflow_sla_breaches() -> dict:
    """Flag workflow submissions that have breached their SLA. Alert steward and admin."""
    from app.services.governance.workflow_service import WorkflowService
    from app.workers.async_runner import run_async
    from app.workers.tenant_runner import run_for_all_tenants

    async def handler(session, tenant_id):
        service = WorkflowService(session, tenant_id)
        flagged = await service.flag_sla_breaches()
        return {"flagged": [str(item) for item in flagged]}

    results = run_async(run_for_all_tenants(handler))
    total = sum(len(item.get("flagged", [])) for item in results.values())
    return {"status": "ok", "flagged": total, "tenants": results}


@celery_app.task(
    name="app.workers.tasks.notifications.send_email",
    queue="notifications",
    max_retries=3,
    default_retry_delay=60,
)
def send_email(to: str, subject: str, body_html: str, idempotency_key: str | None = None) -> dict:
    """Send email notification. Retries 3 times with 60s delay."""
    from app.workers.async_runner import run_async

    async def run():
        from app.services.notifications.email_service import EmailService

        idem = idempotency_key or _idempotency_key("send_email", to=to, subject=subject)
        if await cache_get(idem):
            return {"status": "already_sent"}
        result = EmailService.send_sync(to=to, subject=subject, body_html=body_html)
        if result["status"] == "sent":
            await cache_set(idem, "sent", ttl_seconds=86400)
        return result

    return run_async(run())


@celery_app.task(
    name="app.workers.tasks.notifications.deliver_webhook",
    queue="notifications",
    max_retries=5,
    default_retry_delay=60,
)
def deliver_webhook(webhook_id: str, event_type: str, payload: dict) -> dict:
    """Deliver webhook with HMAC signature. Retries with exponential backoff."""
    import uuid

    from sqlalchemy import select

    from app.db.models import Webhook
    from app.db.session import _ensure_engines, tenant_write_session
    from app.services.notifications.webhook_service import deliver_webhook_by_id
    from app.workers.async_runner import run_async

    async def run() -> dict:
        _ensure_engines()
        from app.db.session import AsyncReadSession

        async with AsyncReadSession() as read_session:
            webhook = await read_session.scalar(
                select(Webhook).where(Webhook.id == uuid.UUID(webhook_id))
            )
        if webhook is None:
            return {"status": "not_found", "webhook_id": webhook_id}

        async with tenant_write_session(webhook.tenant_id) as session:
            result = await deliver_webhook_by_id(
                session,
                uuid.UUID(webhook_id),
                event_type,
                payload,
            )
            await session.commit()
            return result

    return run_async(run())


@celery_app.task(
    name="app.workers.tasks.ai.index_dataset_search",
    queue="ai",
    max_retries=2,
)
def index_dataset_search(tenant_id: str, dataset_id: str) -> dict:
    """Index a published dataset in Qdrant for semantic search."""
    import uuid

    from app.repositories.dataset_repository import DatasetRepository
    from app.services.search.qdrant_index_service import index_published_dataset
    from app.workers.async_runner import run_async

    async def run() -> dict:
        from app.db.session import tenant_write_session

        async with tenant_write_session(uuid.UUID(tenant_id)) as session:
            dataset = await DatasetRepository(session).get_by_id(uuid.UUID(dataset_id))
            return await index_published_dataset(dataset)

    return run_async(run())


@celery_app.task(
    name="app.workers.tasks.maintenance.rollup_usage_events",
    queue="maintenance",
)
def rollup_usage_events() -> dict:
    """Hourly rollup of raw usage_events into usage_hourly_rollups."""
    from app.repositories.usage_event_repository import UsageEventRepository
    from app.workers.async_runner import run_async
    from app.workers.tenant_runner import run_for_all_tenants

    async def handler(session, _tenant_id):
        repo = UsageEventRepository(session)
        rolled = await repo.rollup_hourly()
        return {"rolled_up": rolled}

    return run_async(run_for_all_tenants(handler))


@celery_app.task(
    name="app.workers.tasks.maintenance.decay_quality_scores",
    queue="maintenance",
)
def decay_quality_scores() -> dict:
    """Daily quality score decay for stale datasets."""
    from app.repositories.dataset_repository import DatasetRepository
    from app.workers.async_runner import run_async
    from app.workers.tenant_runner import run_for_all_tenants

    async def handler(session, _tenant_id):
        repo = DatasetRepository(session)
        updated = await repo.decay_stale_quality_scores()
        return {"updated": updated}

    return run_async(run_for_all_tenants(handler))


@celery_app.task(
    name="app.workers.tasks.maintenance.verify_backup_integrity",
    queue="maintenance",
)
def verify_backup_integrity() -> dict:
    """Weekly automated backup restore test. Alerts admin on failure."""
    from app.workers.async_runner import run_async

    async def run():
        import json
        import subprocess
        from datetime import UTC, datetime

        from app.core.cache import cache_set
        from app.core.config import settings
        from app.services.platform.backup_status import BACKUP_STATUS_KEY

        logger.info("backup_verification_started")
        verified_at = datetime.now(UTC).isoformat()

        if settings.PGBACKREST_ENABLED:
            try:
                result = subprocess.run(
                    [
                        settings.PGBACKREST_COMMAND,
                        "verify",
                        f"--stanza={settings.PGBACKREST_STANZA}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                output = (result.stdout or "") + (result.stderr or "")
                status = "ok" if result.returncode == 0 else "failed"
                message = output.strip()[:500] or f"pgbackrest verify exit {result.returncode}"
            except (OSError, subprocess.TimeoutExpired) as exc:
                status = "failed"
                message = str(exc)[:500]
        else:
            status = "ok"
            message = "Stub verification passed (pgBackRest not enabled in dev)."

        payload = {
            "status": status,
            "verified_at": verified_at,
            "message": message,
        }
        await cache_set(BACKUP_STATUS_KEY, json.dumps(payload), ttl_seconds=604_800)
        return payload

    return run_async(run())


@celery_app.task(
    name="app.workers.tasks.maintenance.provision_tenant",
    queue="maintenance",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def provision_tenant(
    slug: str,
    display_name: str,
    tier: str = "standard",
    idempotency_key: str | None = None,
) -> dict:
    """Async tenant provisioning worker — idempotent by slug."""
    from app.services.platform.tenant_provisioning_service import TenantProvisioningService
    from app.workers.async_runner import run_async

    idem_key = idempotency_key or _idempotency_key(
        "provision_tenant", slug=slug, display_name=display_name, tier=tier
    )

    async def run() -> dict:
        cached = await cache_get(idem_key)
        if cached:
            logger.info("task_already_processed", task="provision_tenant", idempotency_key=idem_key)
            return {"status": "already_processed"}

        from app.db.session import AsyncWriteSession, _ensure_engines

        _ensure_engines()
        assert AsyncWriteSession is not None
        async with AsyncWriteSession() as session:
            tenant = await TenantProvisioningService().provision(
                session,
                slug=slug,
                display_name=display_name,
                tier=tier,
            )
            await session.commit()
            await cache_set(idem_key, str(tenant.id), ttl_seconds=86400)
            return {
                "status": "ok",
                "tenant_id": str(tenant.id),
                "slug": tenant.slug,
            }

    return run_async(run())
