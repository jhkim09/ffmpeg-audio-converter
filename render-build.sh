#!/bin/bash
set -e

# 🔹 FFmpeg 설치 디렉토리
FFMPEG_DIR="/opt/render/ffmpeg"

# 🔹 설치 및 환경변수 설정
mkdir -p $FFMPEG_DIR && cd $FFMPEG_DIR
curl -L -o ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf ffmpeg.tar.xz --strip-components=1
export PATH=$FFMPEG_DIR:$PATH

# 🔹 FFmpeg 정상 설치 여부 확인
ffmpeg -version
