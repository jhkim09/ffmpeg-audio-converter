import os
import uuid
import subprocess
import requests
from flask import Flask, request, jsonify, send_from_directory
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 폴더 준비
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ── Redis / Upstash 설정 ───────────────────────────────────────────────
# 예: rediss://default:<PASSWORD>@<HOST>:6379/0?ssl_cert_reqs=CERT_NONE
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()

# Upstash(rediss)인 경우 ssl 옵션을 붙여줍니다. (Kombu가 요구)
if REDIS_URL.startswith("rediss://") and "ssl_cert_reqs=" not in REDIS_URL:
    REDIS_URL += ("&" if "?" in REDIS_URL else "?") + "ssl_cert_reqs=CERT_NONE"

# Celery 인스턴스 (Flask와 분리)
celery = Celery("ffmpeg_tasks", broker=REDIS_URL, backend=REDIS_URL)

# Celery 튜닝 (Upstash 제한 회피 & 안정화)
celery.conf.update(
    task_track_started=True,
    worker_send_task_events=True,
    worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", "2")),
    broker_connection_retry_on_startup=True,
    broker_pool_limit=int(os.getenv("BROKER_POOL_LIMIT", "2")),
    broker_heartbeat=0,  # Upstash와 궁합
    redis_max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "5")),
    result_expires=3600,
)

# rediss일 때 백엔드/브로커 SSL 강제 완화 (Upstash 호환)
if REDIS_URL.startswith("rediss://"):
    celery.conf.broker_use_ssl = {"ssl_cert_reqs": "CERT_NONE"}
    celery.conf.redis_backend_use_ssl = {"ssl_cert_reqs": "CERT_NONE"}

# Slack & 서버 URL
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:5000").rstrip("/")


# ── 오디오 분할 ────────────────────────────────────────────────────────
def split_audio_by_time(input_file, output_prefix, segment_time=900):
    """
    입력 파일을 15분(기본) 단위로 mp3로 직접 분할 생성
    (copy가 아닌 인코딩으로 분할하여 타임스탬프/프레임 문제 완화)
    """
    output_pattern = os.path.join(OUTPUT_FOLDER, f"{output_prefix}_%03d.mp3")
    command = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-f", "segment",
        "-segment_time", str(segment_time),
        "-reset_timestamps", "1",
        "-map", "0:a:0",
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-fflags", "+genpts",
        "-avoid_negative_ts", "make_zero",
        output_pattern
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 분할 오류: {e.stderr or e}")
        return []

    return sorted(
        os.path.join(OUTPUT_FOLDER, f)
        for f in os.listdir(OUTPUT_FOLDER)
        if f.startswith(output_prefix) and f.endswith(".mp3")
    )


# ── Celery 작업 ────────────────────────────────────────────────────────
@celery.task(bind=True)
def convert_audio_task(self, input_file):
    """
    1) 파일을 15분 단위로 바로 mp3 분할
    2) (필요시) 추가 후처리 가능
    3) Slack 알림 전송
    """
    base_name = uuid.uuid4().hex
    print("🔹 오디오 분할/변환 시작")

    parts = split_audio_by_time(input_file, base_name, segment_time=900)
    if not parts:
        return {"status": "failed", "output_files": []}

    # 용량 절약: 원본 업로드 파일 삭제 (선택)
    try:
        if os.path.exists(input_file):
            os.remove(input_file)
    except Exception as e:
        print(f"⚠️ 입력 파일 삭제 실패: {e}")

    output_files = parts  # 이미 mp3로 분할됨

    # Slack 알림
    if SLACK_WEBHOOK_URL and output_files:
        file_links = "\n".join(f"{SERVER_URL}/download/{os.path.basename(f)}" for f in output_files)
        payload = {
            "text": (
                "✅ 오디오 변환 완료!\n\n"
                f"📁 변환된 파일 수: {len(output_files)}개\n"
                f"🔗 다운로드 링크:\n{file_links}"
            )
        }
        try:
            requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
            print("✅ Slack 알림 전송 완료")
        except Exception as e:
            print(f"⚠️ Slack 전송 실패: {e}")

    return {"status": "completed", "output_files": output_files}


# ── API ───────────────────────────────────────────────────────────────
@app.route("/convert", methods=["POST"])
def convert_audio():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(input_path)

    task = convert_audio_task.apply_async(args=[input_path])
    return jsonify({"status": "accepted", "task_id": task.id}), 202


@app.route("/status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = convert_audio_task.AsyncResult(task_id)
    if task.state == "PENDING":
        return jsonify({"status": "pending"})
    if task.state == "FAILURE":
        return jsonify({"status": "failed", "error": str(task.result)})

    if task.state == "SUCCESS":
        # task.result 가 None 이어도 안전
        result = task.result or {}
        return jsonify({"status": "completed", "output_files": result.get("output_files", [])})

    return jsonify({"status": task.state})


@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)


# 개발용 로컬 실행 (Render에선 gunicorn 사용)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
