import os
import uuid
import subprocess
import requests
from flask import Flask, request, jsonify, send_from_directory
from celery import Celery
from dotenv import load_dotenv

# 🔹 환경 변수 로드 (.env 사용 가능)
load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 🔹 Redis 설정 (환경 변수에서 로드)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app.config["CELERY_BROKER_URL"] = REDIS_URL
app.config["CELERY_RESULT_BACKEND"] = REDIS_URL

celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)

# 🔹 Slack Webhook URL (환경 변수 사용)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# 🔹 Slack 알림 함수
def send_slack_notification(message):
    """Slack Webhook을 통해 알림을 전송하는 함수"""
    if SLACK_WEBHOOK_URL:
        payload = {"text": message}
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        print(f"🔔 Slack 알림 전송 상태: {response.status_code}")  # 로그 출력

# 🔹 15분(900초) 단위로 오디오 파일 분할
def split_audio_by_time(input_file, output_prefix, segment_time=900):
    output_pattern = os.path.join(OUTPUT_FOLDER, f"{output_prefix}_%03d.m4a")

    command = [
        "ffmpeg", "-i", input_file, "-f", "segment",
        "-segment_time", str(segment_time), "-c", "copy", output_pattern
    ]
    
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 분할 오류: {e}")
        return []

    split_files = sorted([f for f in os.listdir(OUTPUT_FOLDER) if f.startswith(output_prefix) and f.endswith(".m4a")])
    return [os.path.join(OUTPUT_FOLDER, f) for f in split_files]

# 🔹 Celery 작업: 변환 후 Slack 알림 전송
@celery.task(bind=True)
def convert_audio_task(self, input_file):
    output_files = []
    base_name = uuid.uuid4().hex

    print(f"🔹 파일을 15분 단위로 분할 중...")
    split_files = split_audio_by_time(input_file, base_name)

    if not split_files:
        return {"status": "failed", "error": "File splitting failed"}

    send_slack_notification(f"🔹 변환 작업 시작: {len(split_files)}개 파일 변환 예정")

    for idx, split_file in enumerate(split_files):
        output_file = os.path.join(OUTPUT_FOLDER, f"{base_name}_{idx}.mp3")
        command = [
            "ffmpeg", "-i", split_file,
            "-c:a", "libmp3lame", "-b:a", "128k",
            "-preset", "ultrafast", "-threads", "4",
            "-progress", "pipe:1", output_file
        ]

        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in process.stdout:
                if "out_time_ms" in line:
                    timestamp = int(line.strip().split('=')[-1]) // 1000000
                    print(f"🔹 변환 진행 중: {timestamp}초 변환 완료")
            process.wait()
            output_files.append(output_file)
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg 변환 오류: {e}")

    # 🔹 변환 완료 후 Slack 알림 발송
    if output_files:
        file_list = "\n".join([os.path.basename(f) for f in output_files])
        slack_message = f"✅ 오디오 변환 완료!\n📁 변환된 파일 수: {len(output_files)}개\n🔗 파일 목록:\n{file_list}"
        send_slack_notification(slack_message)
        print("✅ Slack 알림 전송 완료!")

    return {"status": "completed", "output_files": output_files}

# 🔹 파일 업로드 및 변환 API
@app.route("/convert", methods=["POST"])
def convert_audio():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(input_path)

    # 🔹 비동기 변환 작업 실행
    task = convert_audio_task.apply_async(args=[input_path])
    return jsonify({"status": "accepted", "task_id": task.id}), 202

# 🔹 변환 상태 확인 API
@app.route("/status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = convert_audio_task.AsyncResult(task_id)

    if task.state == "PENDING":
        response = {"status": "pending"}
    elif task.state == "SUCCESS":
        response = {"status": "completed", "output_files": task.result["output_files"]}
    else:
        response = {"status": "failed"}

    return jsonify(response)

# 🔹 변환된 파일 다운로드 API
@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
