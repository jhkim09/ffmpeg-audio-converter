import os
import uuid
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from celery import Celery

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Render에서 설정한 REDIS_URL 사용
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app.config["CELERY_BROKER_URL"] = REDIS_URL
app.config["CELERY_RESULT_BACKEND"] = REDIS_URL

celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)

# 📌 오디오 파일을 15분(900초) 단위로 분할하는 함수
def split_audio_by_time(input_file, output_prefix, segment_time=900):
    """FFmpeg을 사용하여 오디오 파일을 15분 단위(900초)로 분할"""
    output_pattern = f"{OUTPUT_FOLDER}/{output_prefix}_%03d.m4a"
    command = [
        "ffmpeg", "-i", input_file, "-f", "segment", "-segment_time", str(segment_time),
        "-c", "copy", output_pattern
    ]
    subprocess.run(command, check=True)
    
    # 분할된 파일 리스트 반환
    split_files = sorted([f for f in os.listdir(OUTPUT_FOLDER) if f.startswith(output_prefix)])
    return [os.path.join(OUTPUT_FOLDER, f) for f in split_files]

# Celery 작업: 15분 단위로 분할 후 MP3 변환
@celery.task(bind=True)
def convert_audio_task(self, input_file):
    output_files = []
    base_name = uuid.uuid4().hex

    # 15분 단위로 파일 분할
    print(f"🔹 파일을 15분 단위로 분할 중...")
    split_files = split_audio_by_time(input_file, base_name)

    # 분할된 각 파일을 MP3로 변환
    for idx, split_file in enumerate(split_files):
        output_file = os.path.join(OUTPUT_FOLDER, f"{base_name}_{idx}.mp3")
        command = ["ffmpeg", "-i", split_file, "-c:a", "libmp3lame", "-b:a", "128k", output_file]
        subprocess.run(command, check=True)
        output_files.append(output_file)

    return {"output_files": output_files}

# 파일 업로드 및 변환 API
@app.route("/convert", methods=["POST"])
def convert_audio():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(input_path)

    # 비동기 변환 작업 실행
    task = convert_audio_task.apply_async(args=[input_path])
    return jsonify({"status": "accepted", "task_id": task.id}), 202

# 변환 상태 확인 API
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

# 변환된 파일 다운로드 API
@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
