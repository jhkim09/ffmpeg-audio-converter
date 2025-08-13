import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery("celery_worker", broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(
    task_track_started=True,
    worker_concurrency=4,
    worker_send_task_events=True
)

@celery.task(bind=True)
def debug_task(self):
    print(f"🔹 [Celery Debug] {self.request!r}")

if __name__ == "__main__":
    print("🚀 Celery Worker 실행")
    celery.worker_main()
