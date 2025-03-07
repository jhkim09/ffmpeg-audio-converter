import os
from celery import Celery
from dotenv import load_dotenv

# 🔹 환경 변수 로드 (.env 사용 가능)
load_dotenv()

# 🔹 Redis URL 설정 (app.py와 동일하게 유지)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 🔹 Celery 설정
celery = Celery("celery_worker", broker=REDIS_URL, backend=REDIS_URL)

# 🔹 Celery 설정 업데이트
celery.conf.update(
    task_track_started=True,  # 작업 시작 여부 추적
    worker_send_task_events=True,  # 작업 이벤트 로깅 활성화
    task_acks_late=True,  # 작업이 확실히 완료될 때까지 ACK 보류 (안정성 증가)
    broker_connection_retry_on_startup=True,  # 시작 시 Redis 연결 재시도
)

# 🔹 Celery 디버깅용 태스크
@celery.task(bind=True)
def debug_task(self):
    print(f"🔹 [Celery Task] 실행 요청: {self.request!r}")

if __name__ == "__main__":
    print("🚀 Celery Worker 실행 중...")
    celery.worker_main(argv=["worker", "--loglevel=info", "--pool=solo"])
