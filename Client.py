# Main client entry point

from asyncio import run
import os
import time
import ujson as json
from core.networking.websocket import websocketClient, cleanup_camera
from core.system.hotspot import HotspotController
from core.camera.controller import Camera
from utils.location import update_location_config
from utils.camera_state import camera_state


def load_local_config():
    path = "config/client_config.json"
    if not os.path.exists(path):
        print(f"Configuration file '{path}' not found. Run 'python Client.py setup' to create it.")
        raise SystemExit(1)
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to read {path}: {e}")
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
        # CLIENT_ID = cfg["client_id"]
        # hotspot = HotspotController()
        # hotspot.startHotspot(ssid=CLIENT_ID, password="telescope")
        
        # Run the main websocket client (camera scanner runs as background task)
        run(websocketClient(cfg))
    except KeyboardInterrupt:
        print("[global] KeyboardInterrupt received, exiting and releasing camera...")
        cleanup_camera()
        HotspotController.stopHotspot()
