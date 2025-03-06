from flask import Flask, request, jsonify
from celery_worker import convert_audio_task  # Celery 백그라운드 작업 추가
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/convert", methods=["POST"])
def convert_audio():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        uploaded_file = request.files["file"]

        # 파일 저장 경로 설정
        input_file = os.path.join(UPLOAD_FOLDER, "input.m4a")
        uploaded_file.save(input_file)

        # 변환 작업을 백그라운드에서 실행
        task = convert_audio_task.apply_async(args=[input_file])

        return jsonify({"status": "accepted", "task_id": task.id}), 202  # 202 Accepted 응답

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/status/<task_id>", methods=["GET"])
def get_status(task_id):
    task = convert_audio_task.AsyncResult(task_id)
    if task.state == "PENDING":
        return jsonify({"status": "pending"}), 202
    elif task.state == "FAILURE":
        return jsonify({"status": "failed", "error": str(task.info)}), 500
    elif task.state == "SUCCESS":
        return jsonify({"status": "completed", "files": task.result}), 200
    return jsonify({"status": task.state}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
