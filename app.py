from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/convert", methods=["POST"])
def convert_audio():
    data = request.json
    file_url = data.get("file_url")

    if not file_url:
        return jsonify({"error": "No file URL provided"}), 400

    input_file = os.path.join(UPLOAD_FOLDER, "input.m4a")
    output_pattern = os.path.join(UPLOAD_FOLDER, "output_%03d.mp3")

    try:
        # 1️⃣ 파일 다운로드
        subprocess.run(["wget", "-O", input_file, file_url], check=True)

        # 2️⃣ 원본 파일의 비트레이트 확인 (kbps)
        bitrate_output = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                                         "-show_entries", "stream=bit_rate", "-of", "csv=p=0", input_file],
                                        capture_output=True, text=True)
        bitrate_kbps = int(bitrate_output.stdout.strip()) // 1000  # bps → kbps 변환

        # 3️⃣ 파일 크기를 20MB 이하로 유지하기 위해 분할 시간 계산
        max_file_size_mb = 20
        segment_time = (max_file_size_mb * 8 * 1024) // bitrate_kbps  # 초 단위

        # 4️⃣ FFmpeg을 사용하여 분할 변환
        subprocess.run(["ffmpeg", "-i", input_file, "-f", "segment", "-segment_time", str(segment_time),
                        "-c", "copy", output_pattern], check=True)

        # 5️⃣ 변환된 MP3 파일 리스트 생성
        split_files = sorted([f for f in os.listdir(UPLOAD_FOLDER) if f.startswith("output_")])
        split_urls = [f"{request.host}/{UPLOAD_FOLDER}/{file}" for file in split_files]

        return jsonify({"status": "success", "split_files": split_urls})

    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"FFmpeg processing failed: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
