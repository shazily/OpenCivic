"""
OpenCivic — Celery configuration.
RULE: JSON serialisation ONLY — NEVER pickle.
6 priority queues: critical > ingest > refresh > ai > notifications > maintenance.
"""

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init
from kombu import Exchange, Queue


@worker_process_init.connect
def _reset_worker_process_state(**_kwargs: object) -> None:
    """Clear pooled clients after Celery prefork so each child creates fresh connections."""
    import app.db.session as session_module
    from app.core.cache import reset_cache_client

    session_module.engine = None
    session_module.read_engine = None
    session_module.AsyncWriteSession = None
    session_module.AsyncReadSession = None
    reset_cache_client()


def _queue(name: str, exchange: Exchange) -> Queue:
    return Queue(
        name,
        exchange,
        routing_key=name,
        queue_arguments={"x-dead-letter-exchange": "opencivic.dlx"},
    )


def make_celery() -> Celery:
    from app.core.config import settings

    app = Celery(
        "opencivic",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        event_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_max_retries=3,
        task_default_retry_delay=60,
    )
    main_exchange = Exchange("opencivic", type="direct")
    dlx = Exchange("opencivic.dlx", type="direct")
    app.conf.task_queues = (
        _queue("critical", main_exchange),
        _queue("ingest", main_exchange),
        _queue("refresh", main_exchange),
        _queue("ai", main_exchange),
        _queue("notifications", main_exchange),
        _queue("maintenance", main_exchange),
        Queue("dead_letter", dlx, routing_key="dead_letter"),
    )
    app.conf.beat_schedule = {
        "staleness-check": {
            "task": "app.workers.tasks.staleness.check_all_datasets",
            "schedule": crontab(minute="*"),
            "options": {"queue": "refresh"},
        },
        "connector-syncs": {
            "task": "app.workers.tasks.connectors.trigger_due_syncs",
            "schedule": crontab(minute="*"),
            "options": {"queue": "refresh"},
        },
        "embargo-check": {
            "task": "app.workers.tasks.governance.check_embargo_releases",
            "schedule": crontab(minute="*"),
            "options": {"queue": "refresh"},
        },
        "sla-check": {
            "task": "app.workers.tasks.governance.check_workflow_sla_breaches",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "notifications"},
        },
        "usage-rollup": {
            "task": "app.workers.tasks.maintenance.rollup_usage_events",
            "schedule": crontab(minute=0),
            "options": {"queue": "maintenance"},
        },
        "backup-verify": {
            "task": "app.workers.tasks.maintenance.verify_backup_integrity",
            "schedule": crontab(day_of_week="sun", hour=2, minute=0),
            "options": {"queue": "maintenance"},
        },
        "circuit-reset": {
            "task": "app.workers.tasks.connectors.attempt_circuit_reset",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "refresh"},
        },
        "quality-decay": {
            "task": "app.workers.tasks.maintenance.decay_quality_scores",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "maintenance"},
        },
    }
    app.autodiscover_tasks(["app.workers.tasks"])
    return app


celery_app = make_celery()
