#!/bin/bash
mkdir -p ~/ffmpeg && cd ~/ffmpeg
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xvf ffmpeg-release-amd64-static.tar.xz
mv ffmpeg-*-static ffmpeg_bin
export PATH=$PATH:~/ffmpeg/ffmpeg_bin
