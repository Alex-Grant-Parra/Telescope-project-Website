import os
from flask import Blueprint, render_template, request, send_file, jsonify, abort
from werkzeug.utils import secure_filename
import zipfile
import io
from datetime import datetime

album_bp = Blueprint("album", __name__, template_folder="../templates")

CAMERA_PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "../camera_photos")

def get_jpeg_files():
    files = []
    for fname in os.listdir(CAMERA_PHOTOS_DIR):
        if fname.lower().endswith(".jpg") or fname.lower().endswith(".jpeg"):
            # Extract date from filename (assume format: IMG_YYYYMMDD_HHMMSS.jpg)
            try:
                date_str = fname.split("_")[1]  # e.g., '20240607'
                date = datetime.strptime(date_str, "%Y%m%d")
            except Exception:
                date = None
            files.append({
                "name": fname,
                "date": date_str if date else "",
                "datetime": date.timestamp() if date else 0,
                "url": f"/album/photo/{secure_filename(fname)}"
            })
    return files

@album_bp.route("/album")
def album():
    sort = request.args.get("sort", "date")
    files = get_jpeg_files()
    if sort == "date":
        files.sort(key=lambda x: x["datetime"], reverse=True)
    return render_template("album.html", photos=files)

@album_bp.route("/album/photos")
def album_photos():
    files = get_jpeg_files()
    files.sort(key=lambda x: x["datetime"], reverse=True)
    return jsonify(files)

@album_bp.route("/album/photo/<filename>")
def album_photo(filename):
    path = os.path.join(CAMERA_PHOTOS_DIR, filename)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path)

@album_bp.route("/album/download", methods=["POST"])
def album_download():
    data = request.json
    files = data.get("files", [])
    if not files:
        abort(400)
    abs_files = []
    for fname in files:
        jpeg_path = os.path.join(CAMERA_PHOTOS_DIR, fname)
        cr2_path = os.path.splitext(jpeg_path)[0] + ".cr2"
        # Always add the jpeg if it exists
        if os.path.isfile(jpeg_path):
            abs_files.append(jpeg_path)
        # Always add the raw file if it exists
        if os.path.isfile(cr2_path):
            abs_files.append(cr2_path)
    # Always zip for consistency
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in abs_files:
            zf.write(f, os.path.basename(f))
    mem_zip.seek(0)
    if len(files) == 1:
        zip_name = f"{os.path.splitext(files[0])[0]}.zip"
    else:
        zip_name = "photos.zip"
    return send_file(
        mem_zip,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name
    )
