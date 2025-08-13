import os
from celery import Celery
from dotenv import load_dotenv

# 🔹 환경 변수 로드 (.env 사용)
load_dotenv()

# 🔹 Redis URL 설정 (Upstash rediss:// 사용 시 TLS 지원)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 🔹 Celery 인스턴스 생성
celery = Celery("celery_worker", broker=REDIS_URL)

# 🔹 Celery 설정
celery.conf.update(
    broker_connection_retry=True,
    broker_connection_max_retries=5,
    broker_connection_retry_delay=5,
    broker_heartbeat=10,  # Upstash 연결 유지에 도움
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    broker_pool_limit=1,  # 🔹 연결 수 최소화 (Upstash 무료 플랜 대응)
    worker_concurrency=2,  # Render 환경 메모리 고려
    worker_prefetch_multiplier=1,  # 안정성 강화
    worker_send_task_events=True,
)

# 🔹 디버그용 테스트 태스크
@celery.task(bind=True)
def debug_task(self):
    print(f"🔹 [Celery Task] Request: {self.request!r}")

if __name__ == "__main__":
    print("🚀 Celery Worker 실행 중...")
    celery.worker_main()
