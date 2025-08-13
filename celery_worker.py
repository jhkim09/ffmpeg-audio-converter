# celery_worker.py
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# 예: Upstash REDIS_URL (rediss 사용 시 ssl_cert_reqs 파라미터 필수)
# 예시: rediss://default:******@xxxxx.upstash.io:6379/0?ssl_cert_reqs=none
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery("ffmpeg_tasks", broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(
    task_track_started=True,
    worker_send_task_events=True,
    broker_connection_retry_on_startup=True,
    worker_concurrency=2,   # Render free/small 플랜이면 낮게 유지 추천
)
