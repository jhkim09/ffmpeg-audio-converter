import os
from celery import Celery
from dotenv import load_dotenv
from kombu import ssl  # TLS Redis 대응을 위한 추가

# 🔹 .env 환경변수 로드
load_dotenv()

# 🔹 Redis 연결 주소 설정
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 🔹 Celery 앱 초기화
celery = Celery("celery_worker", broker=REDIS_URL, backend=REDIS_URL)

# 🔹 TLS Redis일 경우 SSL 설정 추가
if REDIS_URL.startswith("rediss://"):
    ssl_options = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery.conf.broker_use_ssl = ssl_options
    celery.conf.result_backend_use_ssl = ssl_options

# 🔹 기본 Celery 설정
celery.conf.update(
    task_track_started=True,
    worker_concurrency=4,  # 병렬 처리 수 설정
    worker_send_task_events=True,
)

# 🔹 디버깅용 태스크
@celery.task(bind=True)
def debug_task(self):
    print(f"🔍 [Celery Task 실행됨] 요청: {self.request!r}")

if __name__ == "__main__":
    print("🚀 Celery Worker 시작")
    celery.worker_main()
