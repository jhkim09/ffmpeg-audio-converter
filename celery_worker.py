import os
from celery import Celery
from dotenv import load_dotenv

# 🔹 환경 변수 로드 (.env 사용 가능)
load_dotenv()

# 🔹 Redis URL 설정 (app.py와 동일하게 유지)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 🔹 Celery 설정
celery = Celery("celery_worker", broker=REDIS_URL, backend=REDIS_URL)

# 🔹 Celery 작업 실행 로그 출력
celery.conf.update(
    task_track_started=True,  # 작업 시작 여부 추적
    worker_send_task_events=True,  # 작업 이벤트 로깅 활성화
)

# 🔹 Celery 로그 출력 (디버깅용)
@celery.task(bind=True)
def debug_task(self):
    print(f"🔹 [Celery Task] Request: {self.request!r}")

if __name__ == "__main__":
    print("🚀 Celery Worker 실행 중...")
    celery.worker_main()
