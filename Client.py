import asyncio
import websockets
import ujson as json  # Using ujson for faster serialization
from cameraController import Camera
import time
import requests
import os
import subprocess
import sys
import re
import signal

CLIENT_ID = "pi-001"
SERVER_URI = "ws://82.36.204.156:4000"

liveview_enabled = True


# pkill -f gvfs-gphoto2-volume-monitor
# pkill -f gvfsd-gphoto2


CLIENT_ID_FILE = "client_id.json"
SERVER_URL = "http://82.36.204.156"  # Update with your server's URL

# def get_client_id():
#     print(f"[DEBUG] Sending POST request to {SERVER_URL}/client/register")
#     # Check if client_id is already stored locally
#     if os.path.exists(CLIENT_ID_FILE):
#         with open(CLIENT_ID_FILE, "r") as f:
#             data = json.load(f)
#             print(f"[DEBUG] Loaded client_id from file: {data}")
#             return data.get("client_id")
    
#     # If not, register with the server to get a new client_id
#     response = requests.post(f"{SERVER_URL}/client/register")
#     print(f"[DEBUG] Response received: {response.status_code} - {response.text}")
#     if response.status_code == 200:
#         try:
#             resp_json = response.json()
#             print(f"[DEBUG] Response JSON: {resp_json}")
#             client_id = resp_json.get("client_id")
#             if client_id:
#                 # Save the client_id locally for future use
#                 with open(CLIENT_ID_FILE, "w") as f:
#                     json.dump({"client_id": client_id}, f)
#                 return client_id
#             else:
#                 print("[ERROR] No client_id in server response!")
#                 return None
#         except Exception as e:
#             print(f"[ERROR] Failed to parse JSON: {e}")
#             return None
#     else:
#         raise Exception(f"Failed to register with server: {response.text}")
    
# CLIENT_ID = get_client_id()




def get_temperature():
    return 22.7

def echo(message):
    return f"Echo: {message}"

def add(a, b):
    return float(a) + float(b)

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
    # label, value = listArg[0], listArg[1]
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
    print("[liveview] Live view started.")
    return "Live view started"

def stopLiveView():
    global liveview_enabled
    liveview_enabled = False
    print("[liveview] Live view stopped.")
    return "Live view stopped"

function_map = {
    "get_temperature": get_temperature,
    "echo": echo,
    "add": add,
    "getCameraChoices":get_camera_choices,
    "setCameraSetting":setCameraSetting,
    "capturePhoto": capturePhoto,
    "startLiveView": startLiveView,
    "stopLiveView": stopLiveView
}

async def handle_server(ws):
    await ws.send(CLIENT_ID)
    async for message in ws:
        try:
            data = json.loads(message)
            function_name = data.get("function")

            if function_name in function_map:
                func = function_map[function_name]
                args = data.get("args", [])
                result = func(*args)
                response = json.dumps({"result": result, "id": data.get("id")})
            else:
                response = json.dumps({"error": f"Function '{function_name}' not found", "id": data.get("id")})

            await ws.send(response)
        except Exception as e:
            await ws.send(json.dumps({"error": str(e)}))

async def run_client():
    try:
        async with websockets.connect(SERVER_URI, ping_interval=20) as ws:
            print(f"[{CLIENT_ID}] Connected to {SERVER_URI}")
            await handle_server(ws)
    except Exception as e:
        print(f"[run_client] Exception: {e}")

def get_liveview_ws_uri():
    liveViewPort = 8000
    # Extract host from SERVER_URI (e.g., ws://82.36.204.156:8001)
    match = re.match(r"ws://([\w\.-]+):\d+", SERVER_URI)
    if not match:
        raise ValueError("SERVER_URI format invalid")
    host = match.group(1)
    return f"ws://{host}:{liveViewPort}"

async def send_frames():
    global liveview_enabled
    uri = get_liveview_ws_uri()
    JPEG_START = b'\xff\xd8'
    JPEG_END = b'\xff\xd9'
    proc = None
    last_frame_time = 0
    frame_interval = 1 / 10  # 10 FPS

    try:
        async with websockets.connect(uri, max_size=2*1024*1024) as ws:
            await ws.send(CLIENT_ID)
            while True:
                if not liveview_enabled:
                    await asyncio.sleep(0.2)
                    continue
                proc = subprocess.Popen([
                    "gphoto2", "--capture-movie", "--stdout"
                ], stdout=subprocess.PIPE)
                buffer = b''
                try:
                    while liveview_enabled:
                        chunk = proc.stdout.read(4096)
                        if not chunk:
                            break
                        buffer += chunk
                        while True:
                            start = buffer.find(JPEG_START)
                            end = buffer.find(JPEG_END, start)
                            if start != -1 and end != -1 and end > start:
                                now = time.time()
                                if now - last_frame_time >= frame_interval:
                                    jpeg = buffer[start:end+2]
                                    await ws.send(jpeg)
                                    last_frame_time = now
                                buffer = buffer[end+2:]
                            else:
                                break
                        if not liveview_enabled:
                            break
                    proc.terminate()
                    proc.wait()
                except Exception as e:
                    print(f"[send_frames] Inner exception: {e}")
                    if proc:
                        proc.terminate()
                        proc.wait()
    except Exception as e:
        print(f"[send_frames] Exception: {e}")
    finally:
        if proc:
            proc.terminate()
            proc.wait()

async def main():
    try:
        while True:
            try:
                task1 = asyncio.create_task(run_client())
                task2 = asyncio.create_task(send_frames())
                done, pending = await asyncio.wait([task1, task2], return_when=asyncio.FIRST_EXCEPTION)
                for task in pending:
                    task.cancel()
                for task in done:
                    if task.exception():
                        print(f"[main] Task exception: {task.exception()}")
                print("[main] Restarting both tasks in 5 seconds...")
                await asyncio.sleep(5)
            except KeyboardInterrupt:
                print("[main] KeyboardInterrupt received, exiting and releasing camera...")
                break
            except Exception as e:
                print(f"[main] Outer exception: {e}")
                await asyncio.sleep(5)
    finally:
        cleanup_camera()

def cleanup_camera():
    print("[cleanup] Releasing camera and killing all gphoto2 processes...")
    try:
        subprocess.run(["pkill", "-9", "gphoto2"])
    except Exception as e:
        print(f"[cleanup] Error killing gphoto2: {e}")


def handle_exit(signum, frame):
    print(f"[signal] Received signal {signum}, exiting and releasing camera...")
    cleanup_camera()
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[global] KeyboardInterrupt received, exiting and releasing camera...")
        cleanup_camera()
