  # app.py
  import os
  from flask import Flask, request, jsonify, send_from_directory
  from dotenv import load_dotenv
  from celery_worker import convert_audio_task

  load_dotenv()

  app = Flask(__name__)

  UPLOAD_FOLDER = "uploads"
  OUTPUT_FOLDER = "outputs"
  os.makedirs(UPLOAD_FOLDER, exist_ok=True)
  os.makedirs(OUTPUT_FOLDER, exist_ok=True)

  @app.route("/convert", methods=["POST"])
  def convert_audio():
      if "file" not in request.files:
          return jsonify({"error": "No file provided"}), 400
      file = request.files["file"]
      input_path = os.path.join(UPLOAD_FOLDER, file.filename)
      file.save(input_path)

      task = convert_audio_task.apply_async(args=[input_path])
      return jsonify({"status": "accepted", "task_id": task.id}), 202

  @app.route("/status/<task_id>", methods=["GET"])
  def task_status(task_id):
      task = convert_audio_task.AsyncResult(task_id)
      if task.state == "PENDING":
          return jsonify({"status": "pending"})
      if task.state == "SUCCESS":
          res = task.result or {}
          return jsonify({"status": "completed", "output_files": res.get("output_files", [])})
      if task.state == "FAILURE":
          return jsonify({"status": "failed", "error": str(task.result)})
      return jsonify({"status": task.state})

  @app.route("/download/<filename>", methods=["GET"])
  def download_file(filename):
      return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

  if __name__ == "__main__":
      app.run(debug=True)
