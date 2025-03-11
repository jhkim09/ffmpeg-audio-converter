import os
from celery import Celery
from dotenv import load_dotenv

# 🔹 환경 변수 로드 (.env 사용 가능)
load_dotenv()

# 🔹 Redis URL 설정
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 🔹 Celery 설정 (worker_concurrency 추가)
celery = Celery("celery_worker", broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(
    task_track_started=True,
    worker_concurrency=4,  # 🔹 병렬 처리 활성화
    worker_send_task_events=True,
)

# 🔹 Celery 작업 실행 로그 출력
@celery.task(bind=True)
def debug_task(self):
    print(f"🔹 [Celery Task] Request: {self.request!r}")

if __name__ == "__main__":
    print("🚀 Celery Worker 실행 중...")
    celery.worker_main()
