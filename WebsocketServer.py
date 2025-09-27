import asyncio
import websockets
import uuid
import ujson as json  # Faster JSON serialization
import time
import tempfile
import os
import threading
import hashlib
import secrets
from flask import jsonify, request, Response

# WebSocket Configuration - using the same ports as defined in Server.py
commandPort = 4000
LiveViewPort = 8000
WS_IP = os.getenv("WS_IP", "0.0.0.0")  # Use environment variable, default to all interfaces
WS_PORT = commandPort
LIVEVIEW_WS_PORT = LiveViewPort

# Security Configuration
def load_api_tokens():
    """Load API tokens from file"""
    tokens_file = "api_tokens.json"
    if os.path.exists(tokens_file):
        try:
            with open(tokens_file, 'r') as f:
                tokens = json.load(f)
            print(f"[TOKENS] Loaded {len(tokens)} API tokens from {tokens_file}")
            for token, info in tokens.items():
                print(f"[TOKENS] - {info.get('name', 'Unknown')} ({info.get('client_type', 'unknown')})")
            return tokens
        except Exception as e:
            print(f"[WARNING] Failed to load API tokens: {e}")
    
    # Return empty dict if no file or error
    print(f"[WARNING] No API tokens file found. Create '{tokens_file}' or use manage_tokens.py")
    return {}

API_TOKENS = load_api_tokens()

# Rate limiting
client_request_counts = {}
REQUEST_LIMIT_PER_MINUTE = 60

# Global variables
pending = {}
latest_frames = {}
last_frame_log_time = {}
clients = []
clients = []

def authenticate_token(token):
    """Validate client authentication token"""
    return token in API_TOKENS

def check_rate_limit(client_ip):
    """Simple rate limiting check"""
    current_time = time.time()
    minute_key = int(current_time // 60)
    
    if client_ip not in client_request_counts:
        client_request_counts[client_ip] = {}
    
    if minute_key not in client_request_counts[client_ip]:
        client_request_counts[client_ip][minute_key] = 0
    
    client_request_counts[client_ip][minute_key] += 1
    
    # Clean old entries
    old_keys = [k for k in client_request_counts[client_ip].keys() if k < minute_key - 1]
    for k in old_keys:
        del client_request_counts[client_ip][k]
    
    return client_request_counts[client_ip][minute_key] <= REQUEST_LIMIT_PER_MINUTE

def generate_token():
    """Generate a secure token for new clients"""
    return secrets.token_urlsafe(32)

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
    client_ip = ws.remote_address[0] if ws.remote_address else "unknown"
    
    # Rate limiting check
    if not check_rate_limit(client_ip):
        print(f"[SECURITY] Rate limit exceeded for {client_ip}")
        await ws.close(code=4008, reason='Rate limit exceeded')
        return
    
    try:
        # First message should be authentication
        auth_message = await asyncio.wait_for(ws.recv(), timeout=10)
        auth_data = json.loads(auth_message)
        
        token = auth_data.get('token')
        client_id = auth_data.get('client_id')
        
        if not token or not authenticate_token(token):
            print(f"[SECURITY] Authentication failed for {client_ip}")
            await ws.close(code=4001, reason='Authentication failed')
            return
            
        if not client_id:
            print(f"[SECURITY] No client_id provided from {client_ip}")
            await ws.close(code=4002, reason='Client ID required')
            return
            
    except asyncio.TimeoutError:
        print(f"[SECURITY] Authentication timeout for {client_ip}")
        await ws.close(code=4003, reason='Authentication timeout')
        return
    except json.JSONDecodeError:
        print(f"[SECURITY] Invalid JSON from {client_ip}")
        await ws.close(code=4004, reason='Invalid JSON')
        return
    except Exception as e:
        print(f"[SECURITY] Authentication error for {client_ip}: {e}")
        await ws.close(code=4000, reason='Authentication error')
        return
    
    # Authentication successful
    client_manager.add_client(client_id, ws)
    client_type = API_TOKENS[token].get('client_type', 'unknown')
    client_name = API_TOKENS[token].get('name', client_id)
    print(f"[+] {client_name} ({client_type}) connected from {client_ip}")

    try:
        async for message in ws:
            # Rate limiting for each message
            if not check_rate_limit(client_ip):
                print(f"[SECURITY] Rate limit exceeded for {client_id} from {client_ip}")
                break
                
            data = json.loads(message)
            msg_id = data.get("id")
            if msg_id in pending:
                future = pending.pop(msg_id)
                future.set_result(data)
            else:
                print(f"[{client_id}] -> {data}")
    except websockets.exceptions.ConnectionClosed:
        print(f"[-] {client_name} disconnected")
    except json.JSONDecodeError:
        print(f"[SECURITY] Invalid JSON from {client_id}")
    except Exception as e:
        print(f"[ERROR] Error handling {client_id}: {e}")
    finally:
        client_manager.remove_client(client_id)

# WebSocket handler for live view frames from client
async def handle_liveview_client(ws):
    client_ip = ws.remote_address[0] if ws.remote_address else "unknown"
    
    # Rate limiting check
    if not check_rate_limit(client_ip):
        print(f"[SECURITY] LiveView rate limit exceeded for {client_ip}")
        await ws.close(code=4008, reason='Rate limit exceeded')
        return
    
    try:
        # First message should be authentication
        auth_message = await asyncio.wait_for(ws.recv(), timeout=10)
        auth_data = json.loads(auth_message)
        
        token = auth_data.get('token')
        client_id = auth_data.get('client_id')
        
        if not token or not authenticate_token(token):
            print(f"[SECURITY] LiveView authentication failed for {client_ip}")
            await ws.close(code=4001, reason='Authentication failed')
            return
            
        if not client_id:
            print(f"[SECURITY] LiveView no client_id provided from {client_ip}")
            await ws.close(code=4002, reason='Client ID required')
            return
            
    except asyncio.TimeoutError:
        print(f"[SECURITY] LiveView authentication timeout for {client_ip}")
        await ws.close(code=4003, reason='Authentication timeout')
        return
    except json.JSONDecodeError:
        print(f"[SECURITY] LiveView invalid JSON from {client_ip}")
        await ws.close(code=4004, reason='Invalid JSON')
        return
    except Exception as e:
        print(f"[SECURITY] LiveView authentication error for {client_ip}: {e}")
        await ws.close(code=4000, reason='Authentication error')
        return
    
    # Authentication successful
    client_type = API_TOKENS[token].get('client_type', 'unknown')
    client_name = API_TOKENS[token].get('name', client_id)
    print(f"[LiveView] {client_name} ({client_type}) connected from {client_ip}")
    
    try:
        while True:
            try:
                message = await ws.recv()
                latest_frames[client_id] = message
                now = time.time()
                # Only log every 2 seconds per client
                if (client_id not in last_frame_log_time) or (now - last_frame_log_time[client_id] > 2):
                    print(f"[LiveView] Received frame from {client_name}, size: {len(message)} bytes")
                    last_frame_log_time[client_id] = now
            except websockets.exceptions.ConnectionClosed:
                print(f"[LiveView] {client_name} disconnected from live view.")
                break
            except Exception as e:
                print(f"[LiveView] Error receiving frame from {client_name}: {e}")
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
    print("Client requesting client ID")
    client_id = str(uuid.uuid4())
    
    # Generate a secure token for the client
    token = generate_token()
    
    # For now, we'll allow registration but you should add your own authorization logic
    # In production, you might want to require admin approval or other validation
    
    clients.append(client_id)
    
    print(f"[+] New client registered: {client_id}")
    print(f"[SECURITY] Generated token for client (store this securely): {token}")
    
    return jsonify({
        "client_id": client_id,
        "token": token,
        "message": "Store this token securely - you'll need it to connect via WebSocket"
    })

def add_api_token_handler():
    """Handler for /admin/add_token route - for manually adding authorized tokens"""
    data = request.get_json()
    
    # Add your admin authentication here
    # For example: check if request is from admin user
    
    token = data.get('token') or generate_token()
    client_type = data.get('client_type', 'observer')  # telescope, observer
    name = data.get('name', 'Unknown Client')
    
    API_TOKENS[token] = {
        "client_type": client_type,
        "name": name
    }
    
    print(f"[ADMIN] Added API token for {name} ({client_type})")
    
    return jsonify({
        "token": token,
        "client_type": client_type,
        "name": name,
        "message": "Token added successfully"
    })
