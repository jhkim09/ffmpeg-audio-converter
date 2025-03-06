from celery import Celery
import subprocess
import os

app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",  # Redis를 사용하여 백그라운드 작업 관리
    backend="redis://localhost:6379/0"
)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.task
def convert_audio_task(input_file):
    output_pattern = os.path.join(UPLOAD_FOLDER, "output_%03d.mp3")

    # 원본 파일의 비트레이트 확인
    bitrate_output = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                                     "-show_entries", "stream=bit_rate", "-of", "csv=p=0", input_file],
                                    capture_output=True, text=True)

    bitrate_str = bitrate_output.stdout.strip()
    bitrate_kbps = int(bitrate_str) // 1000 if bitrate_str.isdigit() else 128

    segment_time = (20 * 8 * 1024) // bitrate_kbps  # 20MB 이하로 유지

    # FFmpeg 변환 실행
    subprocess.run(["ffmpeg", "-i", input_file, "-f", "segment",
                    "-segment_time", str(segment_time), "-c:a", "libmp3lame",
                    "-b:a", "128k", output_pattern])

    return [f"{UPLOAD_FOLDER}/{file}" for file in os.listdir(UPLOAD_FOLDER) if file.startswith("output_")]
