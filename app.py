import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
from celery import Celery

# Flask 앱 설정
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Render에서 제공하는 REDIS_URL 사용 (없으면 기본값 localhost:6379)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app.config["CELERY_BROKER_URL"] = REDIS_URL
app.config["CELERY_RESULT_BACKEND"] = REDIS_URL

celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)

# Celery 작업: 오디오 변환
@celery.task(bind=True)
def convert_audio_task(self, input_file):
    output_file = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex}.mp3")

    # FFmpeg을 사용하여 M4A → MP3 변환
    command = f'ffmpeg -i "{input_file}" -c:a libmp3lame -b:a 128k "{output_file}"'
    os.system(command)

    return {"output_file": output_file}

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
        response = {"status": "completed", "output_file": task.result["output_file"]}
    else:
        response = {"status": "failed"}

    return jsonify(response)

# 변환된 파일 다운로드 API
@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
