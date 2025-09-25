import asyncio
import websockets
import ujson as json  # Using ujson for faster serialization
import time
import subprocess
import sys
import re
import signal
from function_handlers import function_map, is_liveview_enabled

CLIENT_ID_FILE = "client_id.json"
SERVER_URI = "ws://82.36.204.156:4000"
CLIENT_ID = "pi-001"

async def handle_server(ws):
    """Handle incoming WebSocket messages and execute mapped functions"""
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
    """Run the main WebSocket client"""
    try:
        async with websockets.connect(SERVER_URI, ping_interval=20) as ws:
            print(f"[{CLIENT_ID}] Connected to {SERVER_URI}")
            await handle_server(ws)
    except Exception as e:
        print(f"[run_client] Exception: {e}")

def get_liveview_ws_uri():
    """Generate the live view WebSocket URI"""
    liveViewPort = 8000
    # Extract host from SERVER_URI (e.g., ws://82.36.204.156:8001)
    match = re.match(r"ws://([\w\.-]+):\d+", SERVER_URI)
    if not match:
        raise ValueError("SERVER_URI format invalid")
    host = match.group(1)
    return f"ws://{host}:{liveViewPort}"

async def send_frames():
    """Send live camera frames via WebSocket"""
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
                if not is_liveview_enabled():
                    await asyncio.sleep(0.2)
                    continue
                proc = subprocess.Popen([
                    "gphoto2", "--capture-movie", "--stdout"
                ], stdout=subprocess.PIPE)
                buffer = b''
                try:
                    while is_liveview_enabled():
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
                        if not is_liveview_enabled():
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

def cleanup_camera():
    """Clean up camera processes"""
    print("[cleanup] Releasing camera and killing all gphoto2 processes...")
    try:
        subprocess.run(["pkill", "-9", "gphoto2"])
    except Exception as e:
        print(f"[cleanup] Error killing gphoto2: {e}")

def handle_exit(signum, frame):
    """Handle exit signals"""
    print(f"[signal] Received signal {signum}, exiting and releasing camera...")
    cleanup_camera()
    sys.exit(0)

async def main():
    """Main async function that runs both WebSocket client and frame sender"""
    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)
    
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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[global] KeyboardInterrupt received, exiting and releasing camera...")
        cleanup_camera()