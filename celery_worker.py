import os
import ssl  # ✅ 표준 라이브러리에서 import
from celery import Celery
from dotenv import load_dotenv

# 🔹 .env 로드
load_dotenv()

# 🔹 Redis 설정
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 🔹 Celery 앱 생성
celery = Celery("celery_worker", broker=REDIS_URL, backend=REDIS_URL)

# 🔹 TLS Redis용 SSL 설정
if REDIS_URL.startswith("rediss://"):
    ssl_options = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery.conf.broker_use_ssl = ssl_options
    celery.conf.result_backend_use_ssl = ssl_options

# 🔹 기타 설정
celery.conf.update(
    task_track_started=True,
    worker_concurrency=4,
    worker_send_task_events=True,
)

@celery.task(bind=True)
def debug_task(self):
    print(f"✅ [Celery Debug] Request: {self.request!r}")

if __name__ == "__main__":
    print("🚀 Celery Worker 실행")
    celery.worker_main()
