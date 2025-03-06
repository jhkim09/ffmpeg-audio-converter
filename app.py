from flask import Flask, request, jsonify
import subprocess
import os
import sys  # 로그 출력을 강제 실행하기 위해 필요

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/convert", methods=["POST"])
def convert_audio():
    try:
        data = request.json
        file_url = data.get("file_url")

        if not file_url:
            return jsonify({"error": "No file URL provided"}), 400

        input_file = os.path.join(UPLOAD_FOLDER, "input.m4a")
        output_pattern = os.path.join(UPLOAD_FOLDER, "output_%03d.mp3")

        # 1️⃣ 파일 다운로드
        download_result = subprocess.run(["wget", "-O", input_file, file_url], capture_output=True, text=True)
        print("🔹 Download result:", download_result.stdout, download_result.stderr)
        sys.stdout.flush()  # Render에서 로그가 즉시 표시되도록 강제 출력

        # 2️⃣ 원본 파일의 비트레이트 확인 (kbps)
        bitrate_output = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                                         "-show_entries", "stream=bit_rate", "-of", "csv=p=0", input_file],
                                        capture_output=True, text=True)
        
        bitrate_str = bitrate_output.stdout.strip()
        if not bitrate_str.isdigit():  
            print("⚠️ FFmpeg failed to get bitrate. Using default 128kbps.")
            bitrate_kbps = 128  
        else:
            bitrate_kbps = int(bitrate_str) // 1000  

        sys.stdout.flush()  # 로그 즉시 출력

        # 3️⃣ 파일 크기를 20MB 이하로 유지하기 위해 분할 시간 계산
        max_file_size_mb = 20
        segment_time = (max_file_size_mb * 8 * 1024) // bitrate_kbps  

        # 4️⃣ FFmpeg을 사용하여 변환 (로그를 파일로 저장)
        print("🔹 Running FFmpeg conversion...")
        sys.stdout.flush()  # Render Logs에서 로그 확인

        ffmpeg_result = subprocess.run(["ffmpeg", "-i", input_file, "-f", "segment",
                                        "-segment_time", str(segment_time), "-c:a", "libmp3lame",
                                        "-b:a", "128k", output_pattern], capture_output=True, text=True)
        
        print("🔹 FFmpeg result (stdout):", ffmpeg_result.stdout)
        print("🔹 FFmpeg result (stderr):", ffmpeg_result.stderr)
        sys.stdout.flush()  # 로그 즉시 출력

        # **🔹 변환된 파일 확인**
        split_files = sorted([f for f in os.listdir(UPLOAD_FOLDER) if f.startswith("output_")])
        if not split_files:
            print("⚠️ No files were generated. Check FFmpeg settings.")
            sys.stdout.flush()  # 로그 즉시 출력

        split_urls = [f"{request.host}/{UPLOAD_FOLDER}/{file}" for file in split_files]

        return jsonify({"status": "success", "split_files": split_urls})

    except Exception as e:
        print("🔥 Error:", str(e))
        sys.stdout.flush()  # Render에서 로그를 즉시 볼 수 있도록 강제 출력
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
