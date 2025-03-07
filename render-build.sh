#!/bin/bash
set -e  # 오류 발생 시 즉시 스크립트 종료

# 🔹 FFmpeg 다운로드 및 설치 경로 설정
FFMPEG_DIR="/opt/render/ffmpeg"

# 🔹 기존 FFmpeg 디렉토리가 있다면 삭제 후 재생성
rm -rf $FFMPEG_DIR
mkdir -p $FFMPEG_DIR && cd $FFMPEG_DIR

# 🔹 FFmpeg 다운로드 (최신 공식 경로 사용)
wget -O ffmpeg.tar.xz "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"

# 🔹 압축 해제 및 이동
tar -xvf ffmpeg.tar.xz --strip-components=1
rm -f ffmpeg.tar.xz  # 다운로드된 압축 파일 삭제 (공간 절약)

# 🔹 FFmpeg 실행 경로를 환경 변수에 추가
export PATH=$FFMPEG_DIR:$PATH

# 🔹 FFmpeg 설치 확인
ffmpeg -version
