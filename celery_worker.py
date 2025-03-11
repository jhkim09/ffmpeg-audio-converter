@celery.task(bind=True)
def convert_audio_task(self, input_file):
    output_files = []
    base_name = uuid.uuid4().hex

    print(f"🔹 파일을 15분 단위로 분할 중...")
    split_files = split_audio_by_time(input_file, base_name)

    if not split_files:
        self.update_state(state="FAILURE", meta={"error": "File splitting failed"})
        return {"status": "failed", "output_files": []}

    for idx, split_file in enumerate(split_files):
        output_file = os.path.join(OUTPUT_FOLDER, f"{base_name}_{idx}.mp3")
        command = [
            "ffmpeg", "-i", split_file,
            "-c:a", "libmp3lame", "-b:a", "128k",
            "-preset", "ultrafast", "-threads", "4",
            output_file
        ]

        try:
            subprocess.run(command, check=True)
            output_files.append(os.path.basename(output_file))  # 파일 이름만 저장
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg 변환 오류: {e}")

    # 🔹 상태 업데이트 (작업 진행률 반영)
    self.update_state(state="SUCCESS", meta={"output_files": output_files})

    # 🔹 변환 완료 후 Slack 알림 발송 (파일 다운로드 링크 포함)
    if SLACK_WEBHOOK_URL and output_files:
        file_links = "\n".join([f"{SERVER_URL}/download/{f}" for f in output_files])
        slack_message = {
            "text": f"✅ 오디오 변환 완료!\n\n📁 변환된 파일 수: {len(output_files)}개\n🔗 다운로드 링크:\n{file_links}"
        }
        requests.post(SLACK_WEBHOOK_URL, json=slack_message)
        print("✅ Slack 알림 전송 완료!")

    return {"status": "completed", "output_files": output_files}
