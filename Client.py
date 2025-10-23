# Main client entry point

import asyncio
from websocket_client import websocketClient, cleanup_camera
from bluetooth_client import bluetoothClient
import json
from pathlib import Path

# load connectionType from client_config.json (same dir as this file)
_config_path = Path(__file__).parent / "client_config.json"
connectionType = ""
try:
    with _config_path.open("r", encoding="utf-8") as f:
        _data = json.load(f)
        connectionType = _data.get("connectionType", "")
except FileNotFoundError:
    print(f"[config] {_config_path} not found; using default empty connectionType")
except json.JSONDecodeError as e:
    print(f"[config] failed to parse {_config_path}: {e}; using default empty connectionType")

if __name__ == "__main__":
    try:
        if connectionType == "websocket":
            asyncio.run(websocketClient())
        elif connectionType  == "bluetooth":
            asyncio.run(bluetoothClient())
        else:
            print("Invalid client type in Json")
    except KeyboardInterrupt:
        print("[global] KeyboardInterrupt received, exiting and releasing camera...")
        cleanup_camera()
