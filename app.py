import os
import uuid
import subprocess
import requests
from flask import Flask, request, jsonify, send_from_directory
from celery import Celery
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Flask 앱 생성
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Celery 설정
def make_celery(app):
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery = Celery(
        app.import_name,
        broker=redis_url,
        backend=redis_url,
    )
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

# 슬랙 & 서버 주소
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:5000")

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
    elif task.state == "SUCCESS":
        return jsonify({"status": "completed", "output_files": task.result.get("output_files", [])})
    elif task.state == "FAILURE":
        return jsonify({"status": "failed", "error": str(task.result)})
    else:
        return jsonify({"status": "unknown"})

@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

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

@celery.task(bind=True)
def convert_audio_task(self, input_file):
    output_files = []
    base_name = uuid.uuid4().hex

    print("🔹 15분 단위로 오디오 분할")
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
            print(f"❌ 변환 오류: {e}")

    if SLACK_WEBHOOK_URL and output_files:
        file_links = "\n".join([f"{SERVER_URL}/download/{os.path.basename(f)}" for f in output_files])
        slack_message = {
            "text": f":white_check_mark: 오디오 변환 완료!\n\n:file_folder: 변환된 파일 수: {len(output_files)}개\n:link: 다운로드 링크:\n{file_links}"
        }
        requests.post(SLACK_WEBHOOK_URL, json=slack_message)
        print("✅ Slack 전송 완료")

    return {"status": "completed", "output_files": output_files}
