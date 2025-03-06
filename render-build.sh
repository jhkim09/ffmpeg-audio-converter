#!/bin/bash
# FFmpeg 바이너리 다운로드 경로 변경
mkdir -p /opt/render/ffmpeg && cd /opt/render/ffmpeg
wget -O ffmpeg.tar.xz "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.tar.xz"
tar -xvf ffmpeg.tar.xz --strip-components=1
export PATH=$PATH:/opt/render/ffmpeg
