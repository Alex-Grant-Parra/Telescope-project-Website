import time
import requests
import os
import json
from typing import Optional
from cameraController import Camera # type: ignore

CONFIG_FILE = "client_config.json"

# Default server URL; will be overridden by config if present
SERVER_URL = "https://telescopes.dev"
try:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as cf:
            cfg = json.load(cf)
            SERVER_URL = cfg.get('server_http_url', SERVER_URL)
except Exception:
    # If the config can't be read, continue with default
    pass
LIVEVIEW_STATE_FILE = "liveview_state.json"

# Reusable HTTP session for cookies and connection pooling
SESSION = requests.Session()

# Simple in-memory cache for CSRF token
_CSRF_TOKEN: Optional[str] = None
_CSRF_FETCH_TS: float = 0.0
_CSRF_TTL_SECONDS = 10 * 60  # Refresh every 10 minutes

def _extract_csrf_from_json(data: dict) -> Optional[str]:
    """Try common keys to find a CSRF token in a JSON payload."""
    # Common key names that servers might use
    for key in (
        "csrfToken",
        "csrf_token",
        "token",
        "csrf",
        "xsrfToken",
        "XSRFToken",
    ):
        val = data.get(key)
        if isinstance(val, str) and val:
            return val
    # Fallback: search any string value containing 'csrf' or 'xsrf'
    for k, v in data.items():
        if isinstance(v, str) and ("csrf" in k.lower() or "xsrf" in k.lower()):
            return v
    return None

def get_csrf_token(force_refresh: bool = False) -> Optional[str]:
    """
    Fetch and cache a CSRF token from <SERVER_URL>/security/csrf-token.
    Returns the token string if found, otherwise None. Uses a shared session so
    any cookie-based associations are preserved.
    """
    global _CSRF_TOKEN, _CSRF_FETCH_TS

    now = time.time()
    # If we have a cached token and it's fresh, reuse it only if we still have cookies
    if (
        not force_refresh
        and _CSRF_TOKEN
        and (now - _CSRF_FETCH_TS) < _CSRF_TTL_SECONDS
        and len(SESSION.cookies) > 0
    ):
        return _CSRF_TOKEN

    endpoint = f"{SERVER_URL}/security/csrf-token"
    try:
        resp = SESSION.get(endpoint, timeout=10)
        resp.raise_for_status()
        token = None
        # Try JSON first
        try:
            data = resp.json()
            if isinstance(data, dict):
                token = _extract_csrf_from_json(data)
        except ValueError:
            # Not JSON; try plain text
            text = resp.text.strip()
            if text:
                token = text

        if token:
            _CSRF_TOKEN = token
            _CSRF_FETCH_TS = now
            try:
                # Helpful for debugging cookie presence
                print("[DEBUG] CSRF token obtained; session cookies:", SESSION.cookies.get_dict())
            except Exception:
                pass
            return token
        else:
            print("[WARN] CSRF endpoint responded but no token was found in the payload.")
            return None
    except requests.RequestException as e:
        print(f"[WARN] Failed to fetch CSRF token: {e}")
        return None

def load_liveview_state():
    """Load live view state from file"""
    if os.path.exists(LIVEVIEW_STATE_FILE):
        try:
            with open(LIVEVIEW_STATE_FILE, 'r') as f:
                state = json.load(f)
                return state.get("enabled", False)  # Default to False
        except Exception:
            pass
    return False  # Default to disabled

def save_liveview_state(enabled):
    """Save live view state to file"""
    try:
        with open(LIVEVIEW_STATE_FILE, 'w') as f:
            json.dump({"enabled": enabled}, f)
    except Exception:
        pass

# Load the live view state from file, or default to True
liveview_enabled = load_liveview_state()

def echo(message):
    return f"Echo: {message}"

def get_camera_choices():
    # Map setting names to gphoto2 config paths
    settings = {
        "shutterSpeed": "/main/capturesettings/shutterspeed",
        "iso": "/main/imgsettings/iso",
        # Add more settings as needed
    }
    choices = {}
    start = time.time()
    for label, path in settings.items():
        result = Camera.getSettingChoices(label, path)
        choices[label] = result if result else []
    print(f"get_camera_choices took {time.time() - start:.2f} seconds")
    return choices

def setCameraSetting(label, value):
    Camera.setSetting(label, value)
    return f"Set {label} to {value}"

def capturePhoto(currentid):
    files = Camera.capturePhoto(currentid=currentid) # Returns a list of two file names, one raw, one jpeg

    print(files)

    if not isinstance(files, list) or len(files) < 2:
        print("[ERROR] Camera.capturePhoto() did not return two valid files")
        return

    current_dir = os.getcwd()
    photos_dir = os.path.join(current_dir, "photos/default")

    # Ensure directory exists
    if not os.path.exists(photos_dir):
        print(f"[ERROR] Directory '{photos_dir}' does not exist.")
        return

    # Prepare file paths
    files = [os.path.join(photos_dir, file) for file in files]

    # Verify files exist
    missing_files = [file for file in files if not os.path.exists(file)]
    if missing_files:
        print(f"[ERROR] The following files are missing: {missing_files}")
        return
    
    server_url = f"{SERVER_URL}/upload"

    # Prepare file tuples with filenames and basic content-types
    def _guess_mime(path: str) -> str:
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        if ext in {"jpg", "jpeg"}:
            return "image/jpeg"
        if ext in {"png"}:
            return "image/png"
        if ext in {"gif"}:
            return "image/gif"
        if ext in {"bmp"}:
            return "image/bmp"
        if ext in {"tiff", "tif"}:
            return "image/tiff"
        if ext in {"webp"}:
            return "image/webp"
        # RAW/other
        return "application/octet-stream"

    file_data = {
        f"file{index}": (os.path.basename(file), open(file, "rb"), _guess_mime(file))
        for index, file in enumerate(files)
    }

    # Prepare headers, attach CSRF if available
    headers = {}
    data = None
    token = get_csrf_token()
    if token:
        # Send both common header variations to be safe
        headers["X-CSRF-Token"] = token
        headers["X-CSRFToken"] = token
        # Also include token as form field to support Flask-WTF style
        data = {"csrf_token": token}

    try:
        print("[DEBUG] Sending files to server...")
        response = SESSION.post(
            server_url,
            files=file_data,
            headers=headers,
            data=data,
            timeout=60,
        )
        # Try to print JSON if available, else status/text
        try:
            print("[DEBUG] Server response:", response.json())
        except ValueError:
            print(f"[DEBUG] Server response status={response.status_code}, body={response.text[:300]}")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to upload files: {e}")
    finally:
        # Ensure files are closed
        for f in file_data.values():
            f.close()

def startLiveView():
    global liveview_enabled
    liveview_enabled = True
    save_liveview_state(True)
    print("[liveview] Live view started.")
    return "Live view started"

def stopLiveView():
    global liveview_enabled
    liveview_enabled = False
    save_liveview_state(False)
    
    # Release camera viewfinder using the Camera class
    Camera.releaseViewfinder()
    
    print("[liveview] Live view stopped.")
    return "Live view stopped"

# Function mapping dictionary
function_map = {
    "echo": echo,
    "getCameraChoices": get_camera_choices,
    "setCameraSetting": setCameraSetting,
    "capturePhoto": capturePhoto,
    "startLiveView": startLiveView,
    "stopLiveView": stopLiveView
}

def is_liveview_enabled():
    """Helper function to check liveview status from other modules"""
    return liveview_enabled