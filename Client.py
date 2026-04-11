# Main client entry point

from asyncio import run
import time
from core.networking.websocket import websocketClient, cleanup_camera
from core.camera.controller import Camera
from utils.location import update_location_config
from utils.camera_state import camera_state
from utils.config_state import (
    get_client_config,
    ensure_state_files,
    get_missing_required_client_fields,
)


def _validate_required_client_config() -> None:
    missing = get_missing_required_client_fields()
    if not missing:
        return

    print("\n[config] Missing required client configuration fields.")
    print("[config] Required: client_id, base_url, api_token")
    print("[config] Update config/client_profile.json and rerun Client.py")
    raise SystemExit(78)


def load_local_config():
    try:
        ensure_state_files()
        _validate_required_client_config()
        return get_client_config()
    except Exception as e:
        print(f"Failed to read configuration files: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        # Clean up any lingering processes from previous runs
        print("[startup] Cleaning up previous camera processes...")
        cleanup_camera()
        time.sleep(1)
        
        # Quick non-blocking camera check
        print("[startup] Checking for camera...")
        if Camera.ensureConnection(retryCount=1, delaySeconds=0):
            print("[startup] Camera detected and ready")
            camera_state.set_available(True)
            # Release viewfinder to ensure camera is in clean state
            try:
                Camera.releaseViewfinder()
            except:
                pass
        else:
            print("[startup] Camera not detected - will scan continuously in background")
            print("[startup] Connect camera via USB and it will be detected automatically")
            camera_state.set_available(False)
        
        # Update GPS location on startup
        update_location_config()
        
        cfg = load_local_config()
        
        # Run the main websocket client (camera scanner runs as background task)
        run(websocketClient(cfg))
    except KeyboardInterrupt:
        print("[global] KeyboardInterrupt received, exiting and releasing camera...")
        cleanup_camera()