import time
import requests
import os
import json
from typing import Optional, Any, Dict
from cameraController import Camera # type: ignore
from csrf import get_csrf_token, SESSION
from liveview_state import load_liveview_state, save_liveview_state
from esp32.esp32 import ESP32Motor, ESP32Config

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
    token = get_csrf_token(SERVER_URL)
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

# -----------------------------
# ESP32 motor control handlers
# -----------------------------

_ESP32_INSTANCE: Optional[ESP32Motor] = None

def _get_esp32() -> ESP32Motor:
    global _ESP32_INSTANCE
    if _ESP32_INSTANCE is None:
        # Use defaults from ESP32Config; consider adding config override if needed
        _ESP32_INSTANCE = ESP32Motor(ESP32Config())
    return _ESP32_INSTANCE

def espEnable(on: Any) -> Dict[str, Any]:
    """Enable/disable the stepper driver."""
    try:
        return _get_esp32().enable(bool(on))
    except Exception as e:
        return {"error": str(e)}

def espSetDirection(forward: Any) -> Dict[str, Any]:
    """Set motor direction: True=forward, False=reverse."""
    try:
        return _get_esp32().set_direction(bool(forward))
    except Exception as e:
        return {"error": str(e)}

def espSetSpeed(sps: Any) -> Dict[str, Any]:
    """Set continuous target speed in steps/sec (does not auto-enable)."""
    try:
        return _get_esp32().set_speed(float(sps))
    except Exception as e:
        return {"error": str(e)}

def espStart(sps: Any, forward: Optional[Any] = None) -> Dict[str, Any]:
    """Start continuous rotation at speed; optional direction; auto-enables."""
    try:
        fwd = None if forward is None else bool(forward)
        return _get_esp32().start(float(sps), fwd)
    except Exception as e:
        return {"error": str(e)}

def espMoveSteps(steps: Any, sps: Optional[Any] = None, forward: Optional[Any] = None) -> Dict[str, Any]:
    """Move a finite number of steps; optional speed and direction override."""
    try:
        spd = None if sps is None else float(sps)
        fwd = None if forward is None else bool(forward)
        return _get_esp32().move_steps(int(steps), spd, fwd)
    except Exception as e:
        return {"error": str(e)}

def espStop() -> Dict[str, Any]:
    """Stop motion and disable driver."""
    try:
        return _get_esp32().stop()
    except Exception as e:
        return {"error": str(e)}

def espSetMicrosteps(value: Any) -> Dict[str, Any]:
    """Set TMC2209 microstepping value (e.g., 16, 32)."""
    try:
        return _get_esp32().set_microsteps(int(value))
    except Exception as e:
        return {"error": str(e)}

def espSetCurrent(mA: Any) -> Dict[str, Any]:
    """Set RMS motor current in milliamps."""
    try:
        return _get_esp32().set_current(int(mA))
    except Exception as e:
        return {"error": str(e)}

def espSetMode(mode: Any) -> Dict[str, Any]:
    """Set chopper mode: 'stealth' or 'spread'."""
    try:
        return _get_esp32().set_mode(str(mode))
    except Exception as e:
        return {"error": str(e)}

def espSetAccel(sps2: Any) -> Dict[str, Any]:
    """Set acceleration in steps/sec^2 for ramping."""
    try:
        return _get_esp32().set_accel(float(sps2))
    except Exception as e:
        return {"error": str(e)}

def espStatus() -> Dict[str, Any]:
    """Query ESP32 firmware status."""
    try:
        return _get_esp32().status()
    except Exception as e:
        return {"error": str(e)}

# Function mapping dictionary
function_map = {
    "echo": echo,
    "getCameraChoices": get_camera_choices,
    "setCameraSetting": setCameraSetting,
    "capturePhoto": capturePhoto,
    "startLiveView": startLiveView,
    "stopLiveView": stopLiveView,
    # ESP32 controls
    "espEnable": espEnable,
    "espSetDirection": espSetDirection,
    "espSetSpeed": espSetSpeed,
    "espStart": espStart,
    "espMoveSteps": espMoveSteps,
    "espStop": espStop,
    "espSetMicrosteps": espSetMicrosteps,
    "espSetCurrent": espSetCurrent,
    "espSetMode": espSetMode,
    "espSetAccel": espSetAccel,
    "espStatus": espStatus,
}