import os
import uuid
import subprocess
import requests
from flask import Flask, request, jsonify, send_from_directory
from celery import Celery
from kombu import ssl  # SSL 설정을 위한 import

app = Flask(__name__)

# 🔹 파일 업로드 및 출력 디렉토리
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 🔹 Redis 설정
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app.config["CELERY_BROKER_URL"] = REDIS_URL
app.config["result_backend"] = REDIS_URL

# 🔹 Celery 초기화
celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"], backend=app.config["result_backend"])

# 🔹 SSL 옵션 설정 (TLS redis 사용 시 필수)
if REDIS_URL.startswith("rediss://"):
    ssl_options = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery.conf.broker_use_ssl = ssl_options
    celery.conf.result_backend_use_ssl = ssl_options

# 🔹 환경 변수에서 Slack 및 서버 주소
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:5000")

# 🔹 오디오 분할 함수
def split_audio_by_time(input_file, output_prefix, segment_time=900):
    output_pattern = os.path.join(OUTPUT_FOLDER, f"{output_prefix}_%03d.mp3")
    command = [
        "ffmpeg", "-i", input_file,
        "-f", "segment",
        "-segment_time", str(segment_time),
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-fflags", "+genpts",
        "-avoid_negative_ts", "make_zero",
        output_pattern
    ]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 분할 오류: {e}")
        return []

    return sorted([
        os.path.join(OUTPUT_FOLDER, f)
        for f in os.listdir(OUTPUT_FOLDER)
        if f.startswith(output_prefix)
    ])

# 🔹 Celery 작업: 오디오 변환 및 Slack 알림
@celery.task(bind=True)
def convert_audio_task(self, input_file):
    output_files = []
    base_name = uuid.uuid4().hex

    print(f"🔹 파일을 15분 단위로 분할 중...")
    split_files = split_audio_by_time(input_file, base_name)

    if not split_files:
        return {"status": "failed", "output_files": []}

    for idx, split_file in enumerate(split_files):
        output_file = os.path.join(OUTPUT_FOLDER, f"{base_name}_{idx}.mp3")
        command = [
            "ffmpeg", "-i", split_file,
            "-c:a", "libmp3lame", "-b:a", "128k",
            "-preset", "ultrafast", "-threads", "4",
            output_file
        ]
        try:
            subprocess.run(command, check=True)
            output_files.append(output_file)
            os.remove(split_file)
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg 변환 오류: {e}")

    # 🔹 Slack 알림 전송
    if SLACK_WEBHOOK_URL and output_files:
        file_links = "\n".join([f"{SERVER_URL}/download/{os.path.basename(f)}" for f in output_files])
        slack_message = {
            "text": f"✅ 오디오 변환 완료!\n\n📁 변환된 파일 수: {len(output_files)}개\n🔗 다운로드 링크:\n{file_links}"
        }
        requests.post(SLACK_WEBHOOK_URL, json=slack_message)
        print("✅ Slack 알림 전송 완료!")

    return {"status": "completed", "output_files": output_files}

# 🔹 파일 업로드 엔드포인트
@app.route("/convert", methods=["POST"])
def convert_audio():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(input_path)

    task = convert_audio_task.apply_async(args=[input_path])
    return jsonify({"status": "accepted", "task_id": task.id}), 202

# 🔹 작업 상태 확인 엔드포인트
@app.route("/status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = convert_audio_task.AsyncResult(task_id)

    if task.state == "PENDING":
        response = {"status": "pending"}
    elif task.state == "SUCCESS":
        result = task.result if task.result else {}
        response = {"status": "completed", "output_files": result.get("output_files", [])}
    elif task.state == "FAILURE":
        response = {"status": "failed", "error": str(task.result)}
    else:
        response = {"status": "unknown"}

    return jsonify(response)

# 🔹 다운로드 링크
@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

# 🔹 앱 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
