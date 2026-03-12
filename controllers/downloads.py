import os
from datetime import datetime
from flask import Blueprint, render_template, abort, send_file
from werkzeug.utils import secure_filename

downloads_bp = Blueprint("downloads", __name__)

DOWNLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))


def format_bytes(num_bytes):
    if num_bytes is None:
        return "-"
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def list_zip_versions():
    if not os.path.isdir(DOWNLOADS_DIR):
        return []

    versions = []
    for entry in os.listdir(DOWNLOADS_DIR):
        if not entry.lower().endswith(".zip"):
            continue
        path = os.path.join(DOWNLOADS_DIR, entry)
        if not os.path.isfile(path):
            continue
        try:
            stat = os.stat(path)
        except OSError:
            continue
        version = os.path.splitext(entry)[0]
        versions.append({
            "version": version,
            "filename": entry,
            "path": path,
            "mtime": stat.st_mtime,
            "size_display": format_bytes(stat.st_size),
            "updated": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })

    versions.sort(key=lambda item: item["mtime"], reverse=True)
    return versions


def resolve_version_file(version):
    versions = list_zip_versions()
    if not versions:
        return None, None

    if version == "latest":
        latest = versions[0]
        return latest["path"], latest["filename"]

    requested = version
    if requested.lower().endswith(".zip"):
        requested = requested[:-4]

    for item in versions:
        if item["version"] == requested:
            return item["path"], item["filename"]

    return None, None


@downloads_bp.route("/downloads")
def downloads_home():
    versions = list_zip_versions()
    latest = versions[0]["version"] if versions else None
    return render_template("downloads.html", versions=versions, latest=latest)


@downloads_bp.route("/downloads/latest")
def downloads_latest():
    path, filename = resolve_version_file("latest")
    if not path:
        abort(404)
    return send_file(path, as_attachment=True, download_name=filename)


@downloads_bp.route("/downloads/<version>")
def downloads_version(version):
    safe_version = secure_filename(version)
    if safe_version != version:
        abort(404)

    path, filename = resolve_version_file(version)
    if not path:
        abort(404)
    return send_file(path, as_attachment=True, download_name=filename)
