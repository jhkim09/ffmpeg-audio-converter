from celery import Celery
import subprocess
import os

app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",  # Redis를 브로커로 사용
    backend="redis://localhost:6379/0"
)

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# 🔹 15분 단위로 오디오 파일을 나누는 함수
def split_audio(input_file, output_folder=UPLOAD_FOLDER, segment_time=900):
    os.makedirs(output_folder, exist_ok=True)
    output_pattern = os.path.join(output_folder, "segment_%03d.m4a")
    
    command = [
        "ffmpeg", "-i", input_file, 
        "-f", "segment", "-segment_time", str(segment_time),
        "-c", "copy", output_pattern
    ]
    
    subprocess.run(command, check=True)
    
    return [os.path.join(output_folder, file) for file in sorted(os.listdir(output_folder)) if file.startswith("segment_")]

# 🔹 분할된 오디오 파일을 변환하는 Celery 태스크
@app.task
def convert_audio(input_file):
    output_file = input_file.replace(".m4a", ".mp3").replace(UPLOAD_FOLDER, PROCESSED_FOLDER)

    command = [
        "ffmpeg", "-i", input_file,
        "-b:a", "128k", "-preset", "ultrafast", "-threads", "4", "-vn", output_file
    ]
    
    subprocess.run(command, check=True)
    
    return output_file

# 🔹 메인 변환 함수 (파일 분할 후 병렬 변환)
def process_audio(input_file):
    segments = split_audio(input_file)
    tasks = [convert_audio.delay(segment) for segment in segments]  # 비동기 실행
    return tasks
