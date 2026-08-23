"""Celery application configuration."""

from celery import Celery

from app.core.config import get_settings
from app.core.redis import celery_ssl_config

settings = get_settings()
broker_url = settings.resolved_celery_broker_url
backend_url = settings.resolved_celery_result_backend

celery_app = Celery(
    "monitoring",
    broker=broker_url,
    backend=backend_url,
    include=["app.monitoring.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="monitoring",
)

broker_ssl = celery_ssl_config(broker_url)
if broker_ssl:
    celery_app.conf.broker_use_ssl = broker_ssl

backend_ssl = celery_ssl_config(backend_url)
if backend_ssl:
    celery_app.conf.redis_backend_use_ssl = backend_ssl
