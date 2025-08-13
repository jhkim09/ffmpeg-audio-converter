#!/bin/bash
set -e

# remember current dir (Render 기본 작업경로: /opt/render/project/src)
pushd .

FFMPEG_DIR="/opt/render/ffmpeg"
rm -rf "$FFMPEG_DIR"
mkdir -p "$FFMPEG_DIR"
cd "$FFMPEG_DIR"

# Install FFmpeg (static build)
wget -O ffmpeg.tar.xz "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
tar -xvf ffmpeg.tar.xz --strip-components=1
rm -f ffmpeg.tar.xz

# back to project dir
popd


# 서버 & 워커 실행
# - Upstash 연결과 충돌 줄이기 위해 Celery를 solo/pool 제한 + 낮은 concurrency
gunicorn -w 4 -b 0.0.0.0:5000 app:app &
celery -A celery_worker worker --loglevel=info --pool=solo --concurrency=2
