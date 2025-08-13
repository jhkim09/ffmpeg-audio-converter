import os
from celery import Celery
from dotenv import load_dotenv

# 🔹 .env 환경 변수 불러오기
load_dotenv()

# 🔹 Redis URL 설정 (TLS 포함)
REDIS_URL = os.getenv("REDIS_URL", "rediss://localhost:6379/0")

# 🔹 Celery 앱 생성
celery = Celery("celery_worker", broker=REDIS_URL, backend=REDIS_URL)

# 🔹 Redis TLS 연결 설정 (Upstash 대응용)
if REDIS_URL.startswith("rediss://"):
    celery.conf.broker_use_ssl = {
        "ssl_cert_reqs": "none"  # Upstash는 인증서 필요 없음
    }
    celery.conf.result_backend_use_ssl = {
        "ssl_cert_reqs": "none"
    }

# 🔹 재시도 간격 설정 (연결 실패 시 무한 재시도 방지)
celery.conf.broker_transport_options = {
    "max_retries": 5,
    "interval_start": 0,
    "interval_step": 0.5,
    "interval_max": 1
}

# 🔹 워커 관련 설정
celery.conf.update(
    task_track_started=True,
    worker_concurrency=2,           # 동시 처리 개수 제한
    worker_send_task_events=True
)

# 🔹 테스트용 태스크 정의
@celery.task(bind=True)
def debug_task(self):
    print(f"🔹 [Celery Task] Request: {self.request!r}")

# 🔹 CLI 실행 시 워커 작동
if __name__ == "__main__":
    print("🚀 Celery Worker 실행 중...")
    celery.worker_main()
