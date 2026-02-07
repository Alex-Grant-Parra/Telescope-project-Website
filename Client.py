# Main client entry point

from asyncio import run
import os
import ujson as json
from core.networking.websocket import websocketClient, cleanup_camera
from core.system.hotspot import HotspotController
from utils.location import update_location_config


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
        # Update GPS location on startup
        update_location_config()
        
        cfg = load_local_config()
        # CLIENT_ID = cfg["client_id"]
        # hotspot = HotspotController()
        # hotspot.startHotspot(ssid=CLIENT_ID, password="telescope")
        run(websocketClient(cfg))
    except KeyboardInterrupt:
        print("[global] KeyboardInterrupt received, exiting and releasing camera...")
        cleanup_camera()
        HotspotController.stopHotspot()
