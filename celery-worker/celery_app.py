"""
Celery App — งานหนัก: AI วิเคราะห์ภาพ + Video processing
"""

import os
from celery import Celery

app = Celery("tasks")

app.conf.update(
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0"),
    result_backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=3600,       # hard limit 1 ชม.
    task_soft_time_limit=3000,  # soft limit 50 นาที
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,  # restart worker หลังทำ 50 tasks (ป้องกัน memory leak)
)

# Import tasks explicitly
import tasks.video_analysis  # noqa: F401
