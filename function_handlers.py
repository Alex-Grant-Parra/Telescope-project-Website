import time
import requests
import os
import json
from cameraController import Camera # type: ignore

SERVER_URL = "https://telescopes.dev"  # Update with your server's URL
LIVEVIEW_STATE_FILE = "liveview_state.json"

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

    file_data = {f"file{index}": open(file, "rb") for index, file in enumerate(files)}

    try:
        print("[DEBUG] Sending files to server...")
        response = requests.post(server_url, files=file_data)
        print("[DEBUG] Server response:", response.json())
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