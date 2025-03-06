#!/bin/bash
# FFmpeg 다운로드 및 설치 (올바른 다운로드 경로 사용)
mkdir -p /opt/render/ffmpeg && cd /opt/render/ffmpeg
wget -O ffmpeg.tar.xz "https://www.johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
tar -xvf ffmpeg.tar.xz --strip-components=1
export PATH=$PATH:/opt/render/ffmpeg
