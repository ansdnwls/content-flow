from celery import Celery
from celery.schedules import crontab
from celery.signals import task_postrun

from app.config import get_settings
from app.core.metrics import record_celery_task
from app.core.sentry_init import init_sentry

settings = get_settings()
init_sentry(settings=settings, runtime="worker")

celery_app = Celery(
    "contentflow",
    broker=settings.effective_celery_broker_url,
    backend=settings.effective_celery_result_backend,
)

celery_app.conf.update(
    task_default_queue="contentflow.default",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    imports=(
        "app.workers.analytics_worker",
        "app.workers.billing_worker",
        "app.workers.bomb_worker",
        "app.workers.comment_worker",
        "app.workers.data_export_worker",
        "app.workers.post_worker",
        "app.workers.retention_worker",
        "app.workers.schedule_worker",
        "app.workers.shorts_worker",
        "app.workers.token_refresh_worker",
        "app.workers.video_worker",
        "app.workers.webhook_retry_worker",
        "app.workers.trending_worker",
        "app.workers.scheduler",
        "app.workers.shopsync_bulk_worker",
        "app.workers.onboarding_worker",
        "app.workers.sheets_upload_worker",
    ),
    beat_schedule={
        "schedule-due-posts-every-minute": {
            "task": "contentflow.schedule_due_posts",
            "schedule": 60.0,
        },
        "collect-comments-periodically": {
            "task": "contentflow.collect_comments",
            "schedule": float(settings.comment_poll_interval_seconds),
        },
        "auto-reply-comments-periodically": {
            "task": "contentflow.auto_reply_comments",
            "schedule": float(settings.comment_poll_interval_seconds),
        },
        "run-due-schedules-every-minute": {
            "task": "contentflow.run_due_schedules",
            "schedule": 60.0,
        },
        "collect-analytics-daily": {
            "task": "contentflow.collect_analytics",
            "schedule": 86400.0,
        },
        "refresh-oauth-tokens-every-10-minutes": {
            "task": "contentflow.refresh_oauth_tokens",
            "schedule": 600.0,
        },
        "retry-webhook-deliveries-every-minute": {
            "task": "contentflow.retry_webhook_deliveries",
            "schedule": 60.0,
        },
        "refresh-trending-topics-hourly": {
            "task": "contentflow.refresh_trending_topics",
            "schedule": 3600.0,
        },
        "check-past-due-subscriptions-daily": {
            "task": "contentflow.check_past_due_subscriptions",
            "schedule": 86400.0,
        },
        "run-retention-policies-daily": {
            "task": "contentflow.run_retention_policies",
            "schedule": crontab(hour=3, minute=0),
        },
        "send-onboarding-emails-every-30-minutes": {
            "task": "contentflow.send_onboarding_emails",
            "schedule": 1800.0,
        },
        "poll-sheets-and-upload-video": {
            "task": "contentflow.poll_sheets_and_upload",
            "schedule": float(settings.sheets_poll_interval_seconds),
        },
    },
)


@task_postrun.connect
def _record_task_metrics(task_id=None, task=None, state=None, **kwargs) -> None:
    if task is None:
        return
    record_celery_task(task.name, (state or "unknown").lower())
