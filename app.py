import os
import uuid
import subprocess
import requests
import time
import gc  # 가비지 컬렉션을 위한 모듈
from threading import Timer  # 특정 시간 후 실행
from flask import Flask, request, jsonify, send_from_directory
from celery import Celery

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 🔹 Redis 설정
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app.config["CELERY_BROKER_URL"] = REDIS_URL
app.config["CELERY_RESULT_BACKEND"] = REDIS_URL

celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)

# 🔹 Slack Webhook URL (환경 변수로 설정)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:5000")  # Render 배포 주소 설정

# 🔹 Celery 작업 후 메모리 해제 함수 (10분 후 실행)
def terminate_worker():
    print("🔹 메모리 해제 및 Celery 워커 재시작")
    os.system("pkill -9 celery")  # Celery 프로세스 강제 종료
    os.system("celery -A app.celery worker --loglevel=info &")  # Celery 다시 실행
    gc.collect()  # 가비지 컬렉션 실행

# 🔹 변환 상태 확인 API
@app.route("/status/<task_id>", methods=["GET"])
def task_status(task_id):
    task = convert_audio_task.AsyncResult(task_id)

    if task.state == "PENDING":
        response = {"status": "pending"}
    elif task.state == "SUCCESS":
        try:
            result = task.get(timeout=1)  # 명확하게 결과 가져오기
            response = {
                "status": "completed",
                "output_files": result.get("output_files", []) if result else []
            }
        except Exception as e:
            response = {"status": "failed", "error": str(e)}
    elif task.state == "FAILURE":
        response = {"status": "failed", "error": str(task.result)}
    else:
        response = {"status": "unknown"}

    return jsonify(response)


# 🔹 15분 단위로 오디오 파일 분할
def split_audio_by_time(input_file, output_prefix, segment_time=900):
    output_pattern = os.path.join(OUTPUT_FOLDER, f"{output_prefix}_%03d.m4a")

    command = [
        "ffmpeg", "-i", input_file, "-f", "segment",
        "-segment_time", str(segment_time), "-c", "copy", output_pattern
    ]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"✅ FFmpeg 분할 완료: {output_pattern}")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 분할 오류: {e}")
        return []

    split_files = sorted([f for f in os.listdir(OUTPUT_FOLDER) if f.startswith(output_prefix) and f.endswith(".m4a")])
    return [os.path.join(OUTPUT_FOLDER, f) for f in split_files]

# 🔹 Celery 작업: 변환 후 Slack 알림 + 메모리 리셋 예약
@celery.task(bind=True)
def convert_audio_task(self, input_file):
    output_files = []
    base_name = uuid.uuid4().hex

    print(f"🔹 파일을 15분 단위로 분할 중...")
    split_files = split_audio_by_time(input_file, base_name)

    if not split_files:
        print("❌ 파일 분할 실패! FFmpeg 오류 가능성 있음.")
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
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(f"✅ FFmpeg 변환 완료: {output_file}")
            print(result.stdout)  # FFmpeg 실행 로그 출력
            print(result.stderr)  # FFmpeg 오류 로그 출력

            if os.path.exists(output_file):
                output_files.append(output_file)
            else:
                print(f"❌ 변환된 파일이 없음: {output_file}")

        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg 변환 오류: {e}")
            print(e.stderr)

    if not output_files:
        print("❌ 변환된 파일이 없음!")
        return {"status": "failed", "output_files": []}

    # 🔹 변환 완료 후 Slack 알림 발송 (파일 다운로드 링크 포함)
    if SLACK_WEBHOOK_URL:
        if output_files:
            file_links = "\n".join([f"{SERVER_URL}/download/{os.path.basename(f)}" for f in output_files])
            slack_message = {
                "text": f"✅ 오디오 변환 완료!\n\n📁 변환된 파일 수: {len(output_files)}개\n🔗 다운로드 링크:\n{file_links}"
            }
        else:
            slack_message = {"text": "⚠️ 변환이 완료되었지만 파일이 없습니다. 오류 로그를 확인하세요."}
        requests.post(SLACK_WEBHOOK_URL, json=slack_message)
        print("✅ Slack 알림 전송 완료!")

    # 🔹 10분 후 Celery 메모리 해제
    Timer(600, terminate_worker).start()

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

# 🔹 변환된 파일 다운로드 API
@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
