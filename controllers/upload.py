import os
from flask import Blueprint, request, jsonify

upload_bp = Blueprint("upload", __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "camera_photos")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Ensure the folder exists

@upload_bp.route('/upload', methods=['POST'])
def upload_file():
    print("\n=== [DEBUG] Upload request received ===")
    print(f"Headers: {request.headers}")
    print(f"Files Received: {request.files.keys()}")

    if not request.files:
        print("[ERROR] No files in request.")
        return jsonify({"status": "error", "message": "No files provided"}), 400

    saved_files = []
    for file_key, file in request.files.items():
        filename = file.filename
        print(f"[DEBUG] Processing file: {filename}")

        if filename == '':
            print("[ERROR] Empty filename detected.")
            return jsonify({"status": "error", "message": "Empty filename provided"}), 400

        save_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            file.save(save_path)
            print(f"[DEBUG] Saved '{filename}' to '{UPLOAD_FOLDER}'")

            # Verify the file was saved
            if not os.path.exists(save_path):
                print(f"[ERROR] File '{filename}' was not saved properly.")
                return jsonify({"status": "error", "message": f"Failed to save '{filename}'"}), 500

            saved_files.append(filename)
        except Exception as e:
            print(f"[ERROR] Failed to save '{filename}': {e}")
            return jsonify({"status": "error", "message": f"Error saving '{filename}'"}), 500

    print("[DEBUG] Upload successful")
    return jsonify({"status": "success", "message": f"Files uploaded to 'camera_photos': {saved_files}"}), 200
