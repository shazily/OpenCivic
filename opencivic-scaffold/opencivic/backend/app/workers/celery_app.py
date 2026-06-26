"""
OpenCivic — Celery configuration.
RULE: JSON serialisation ONLY — NEVER pickle.
6 priority queues: critical > ingest > refresh > ai > notifications > maintenance.
"""
from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

def make_celery() -> Celery:
    from app.core.config import settings
    app = Celery("opencivic", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)
    app.conf.update(
        task_serializer="json", result_serializer="json", accept_content=["json"],
        event_serializer="json", timezone="UTC", enable_utc=True,
        task_acks_late=True, task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1, task_max_retries=3, task_default_retry_delay=60,
    )
    dlx = Exchange("opencivic.dlx", type="direct")
    app.conf.task_queues = (
        Queue("critical",      Exchange("opencivic", type="direct"), routing_key="critical",      queue_arguments={"x-dead-letter-exchange": "opencivic.dlx"}),
        Queue("ingest",        Exchange("opencivic", type="direct"), routing_key="ingest",        queue_arguments={"x-dead-letter-exchange": "opencivic.dlx"}),
        Queue("refresh",       Exchange("opencivic", type="direct"), routing_key="refresh",       queue_arguments={"x-dead-letter-exchange": "opencivic.dlx"}),
        Queue("ai",            Exchange("opencivic", type="direct"), routing_key="ai",            queue_arguments={"x-dead-letter-exchange": "opencivic.dlx"}),
        Queue("notifications", Exchange("opencivic", type="direct"), routing_key="notifications", queue_arguments={"x-dead-letter-exchange": "opencivic.dlx"}),
        Queue("maintenance",   Exchange("opencivic", type="direct"), routing_key="maintenance",   queue_arguments={"x-dead-letter-exchange": "opencivic.dlx"}),
        Queue("dead_letter",   dlx, routing_key="dead_letter"),
    )
    app.conf.beat_schedule = {
        "staleness-check":         {"task": "app.workers.tasks.tasks.check_all_datasets",        "schedule": crontab(minute="*"),           "options": {"queue": "refresh"}},
        "connector-syncs":         {"task": "app.workers.tasks.tasks.trigger_due_syncs",         "schedule": crontab(minute="*"),           "options": {"queue": "refresh"}},
        "embargo-check":           {"task": "app.workers.tasks.tasks.check_embargo_releases",    "schedule": crontab(minute="*"),           "options": {"queue": "refresh"}},
        "sla-check":               {"task": "app.workers.tasks.tasks.check_workflow_sla_breaches","schedule": crontab(minute="*/15"),        "options": {"queue": "notifications"}},
        "usage-rollup":            {"task": "app.workers.tasks.tasks.rollup_usage_events",       "schedule": crontab(minute=0),             "options": {"queue": "maintenance"}},
        "backup-verify":           {"task": "app.workers.tasks.tasks.verify_backup_integrity",   "schedule": crontab(day_of_week="sun", hour=2, minute=0), "options": {"queue": "maintenance"}},
        "circuit-reset":           {"task": "app.workers.tasks.tasks.attempt_circuit_reset",     "schedule": crontab(minute="*/5"),         "options": {"queue": "refresh"}},
        "quality-decay":           {"task": "app.workers.tasks.tasks.decay_quality_scores",      "schedule": crontab(hour=3, minute=0),     "options": {"queue": "maintenance"}},
    }
    app.autodiscover_tasks(["app.workers.tasks"])
    return app

celery_app = make_celery()
