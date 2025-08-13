# app.py
import os
import uuid
import subprocess
import requests
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from celery_worker import celery  # <- 핵심: 여기서 import

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:5000")

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

    return sorted(
        os.path.join(OUTPUT_FOLDER, f)
        for f in os.listdir(OUTPUT_FOLDER)
        if f.startswith(output_prefix)
    )

@celery.task(bind=True)
def convert_audio_task(self, input_file):
    output_files = []
    base_name = uuid.uuid4().hex

    print("🔹 오디오 파일 분할 중...")
    split_files = split_audio_by_time(input_file, base_name)
    if not split_files:
        return {"status": "failed", "output_files": []}

    for idx, split_file in enumerate(split_files):
        output_file = os.path.join(OUTPUT_FOLDER, f"{base_name}_{idx}.mp3")
        cmd = [
            "ffmpeg", "-i", split_file,
            "-c:a", "libmp3lame", "-b:a", "128k",
            "-preset", "ultrafast", "-threads", "2",
            output_file
        ]
        try:
            subprocess.run(cmd, check=True)
            output_files.append(output_file)
            os.remove(split_file)  # 분할본 즉시 삭제 (용량 절약)
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg 변환 오류: {e}")

    if SLACK_WEBHOOK_URL and output_files:
        links = "\n".join(f"{SERVER_URL}/download/{os.path.basename(p)}" for p in output_files)
        try:
            requests.post(SLACK_WEBHOOK_URL, json={
                "text": f"✅ 오디오 변환 완료!\n\n📁 변환된 파일 수: {len(output_files)}개\n🔗 다운로드 링크:\n{links}"
            })
            print("✅ Slack 알림 전송 완료")
        except Exception as e:
            print(f"⚠️ Slack 전송 실패: {e}")

    return {"status": "completed", "output_files": output_files}

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
    if task.state == "SUCCESS":
        res = task.result or {}
        return jsonify({"status": "completed", "output_files": res.get("output_files", [])})
    if task.state == "FAILURE":
        return jsonify({"status": "failed", "error": str(task.result)})
    return jsonify({"status": task.state})

@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

# gunicorn이 사용할 엔트리포인트: app:app
