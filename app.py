from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/split", methods=["POST"])
def split_audio():
    data = request.json
    file_url = data.get("file_url")
    segment_time = data.get("segment_time", 600)  # 기본값: 10분(600초)

    if not file_url:
        return jsonify({"error": "No file URL provided"}), 400

    input_file = os.path.join(UPLOAD_FOLDER, "input.m4a")
    output_pattern = os.path.join(UPLOAD_FOLDER, "split_%03d.m4a")

    try:
        # 파일 다운로드
        subprocess.run(["wget", "-O", input_file, file_url], check=True)

        # FFmpeg으로 파일 분할
        subprocess.run(["ffmpeg", "-i", input_file, "-f", "segment", "-segment_time", str(segment_time), "-c", "copy", output_pattern], check=True)

        # 분할된 파일 목록 반환
        split_files = sorted([f for f in os.listdir(UPLOAD_FOLDER) if f.startswith("split_")])
        split_urls = [f"{request.host}/{UPLOAD_FOLDER}/{file}" for file in split_files]

        return jsonify({"status": "success", "split_files": split_urls})

    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"FFmpeg processing failed: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
