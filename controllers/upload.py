import os
from flask import Blueprint, request, jsonify

upload_bp = Blueprint("upload", __name__)

BASE_UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "camera_photos")
os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)  # Ensure the base folder exists

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

        # Extract user ID (assuming format: "<user_id>_photo_<timestamp>.jpg")
        parts = filename.split("_", 1)
        if len(parts) < 2 or not parts[0].isdigit():
            print("[ERROR] Invalid filename format.")
            return jsonify({"status": "error", "message": "Invalid filename format"}), 400

        user_id = parts[0]  # Extract user ID
        clean_filename = parts[1].replace("_", "")  # Remove underscores from the remaining filename

        user_upload_folder = os.path.join(BASE_UPLOAD_FOLDER, user_id)
        os.makedirs(user_upload_folder, exist_ok=True)  # Ensure the user's folder exists

        save_path = os.path.join(user_upload_folder, clean_filename)
        try:
            file.save(save_path)
            print(f"[DEBUG] Saved '{clean_filename}' to '{user_upload_folder}'")

            # Verify the file was saved
            if not os.path.exists(save_path):
                print(f"[ERROR] File '{clean_filename}' was not saved properly.")
                return jsonify({"status": "error", "message": f"Failed to save '{clean_filename}'"}), 500

            saved_files.append(clean_filename)
        except Exception as e:
            print(f"[ERROR] Failed to save '{clean_filename}': {e}")
            return jsonify({"status": "error", "message": f"Error saving '{clean_filename}'"}), 500

    print("[DEBUG] Upload successful")
    return jsonify({"status": "success", "message": f"Files uploaded to '{user_upload_folder}': {saved_files}"}), 200
