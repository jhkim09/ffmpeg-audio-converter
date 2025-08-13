#!/bin/bash
set -e

FFMPEG_DIR="/opt/render/ffmpeg"
rm -rf $FFMPEG_DIR
mkdir -p $FFMPEG_DIR && cd $FFMPEG_DIR

wget -O ffmpeg.tar.xz "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
tar -xvf ffmpeg.tar.xz --strip-components=1
rm -f ffmpeg.tar.xz

export PATH=$FFMPEG_DIR:$PATH
ffmpeg -version

# Flask + Celery 실행
gunicorn -w 4 -b 0.0.0.0:5000 app:app & \
celery -A celery_worker worker --loglevel=info --pool=solo --concurrency=2
