import os
from celery import Celery
import time
import subprocess
from dotenv import load_dotenv

# 🔹 환경 변수 로드
load_dotenv()

# 🔹 Redis URL 설정 (app.py와 동일하게 유지)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 🔹 Celery 설정
celery = Celery("celery_worker", broker=REDIS_URL, backend=REDIS_URL)

# 🔹 Celery 실행 중인지 체크 후 필요하면 재시작
def check_and_restart_celery():
    while True:
        result = subprocess.run(["pgrep", "-f", "celery"], capture_output=True, text=True)
        if not result.stdout.strip():
            print("⚠️ Celery Worker가 중지됨. 다시 시작합니다...")
            os.system("celery -A app.celery worker --loglevel=info &")
        time.sleep(600)  # 10분마다 점검

# 🔹 Celery 실행 로그 출력
if __name__ == "__main__":
    print("🚀 Celery Worker 실행 중...")
    check_and_restart_celery()
