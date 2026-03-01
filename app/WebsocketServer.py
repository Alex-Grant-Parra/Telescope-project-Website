import asyncio
import websockets
import uuid
import ujson as json  # Faster JSON serialization
import time
import tempfile
import os
import threading
import secrets
import logging
from flask import jsonify, request, Response
from flask_login import current_user

# WebSocket Configuration - using the same ports as defined in Server.py
commandPort = 4000
LiveViewPort = 8000
WS_IP = os.getenv("WS_IP", "0.0.0.0")  # Use environment variable, default to all interfaces
WS_PORT = commandPort
LIVEVIEW_WS_PORT = LiveViewPort
WS_PING_INTERVAL = int(os.getenv("WS_PING_INTERVAL", "20"))
WS_PING_TIMEOUT = int(os.getenv("WS_PING_TIMEOUT", "120"))

sec_logger = logging.getLogger('security')

# Rate limiting
client_request_counts = {}
REQUEST_LIMIT_PER_MINUTE = 60

# Global variables
pending = {}
latest_frames = {}
last_frame_log_time = {}
clients = []
clients = []
heartbeat_tasks = {}  # Store heartbeat tasks by client_id
ws_event_loop = None  # Store reference to WebSocket thread's event loop

_handshake_log_lock = threading.Lock()
_handshake_reject_count = 0
_handshake_last_summary = 0.0
_HANDSHAKE_LOG_WINDOW_SECONDS = 30


def _log_handshake_reject_summary():
    """Log throttled summary for invalid websocket handshake attempts."""
    global _handshake_reject_count, _handshake_last_summary
    now = time.time()

    with _handshake_log_lock:
        _handshake_reject_count += 1
        if now - _handshake_last_summary >= _HANDSHAKE_LOG_WINDOW_SECONDS:
            print(
                f"[WebSocket] Ignored {_handshake_reject_count} invalid handshake request(s) "
                f"in the last {_HANDSHAKE_LOG_WINDOW_SECONDS}s"
            )
            _handshake_reject_count = 0
            _handshake_last_summary = now


class _WebSocketHandshakeNoiseFilter(logging.Filter):
    """Suppress noisy traceback logs for malformed/non-upgrade websocket probes."""

    def filter(self, record):
        message = record.getMessage().lower()

        if "opening handshake failed" in message:
            _log_handshake_reject_summary()
            return False

        if record.exc_info:
            exc_text = str(record.exc_info[1]).lower() if record.exc_info[1] else ""
            if (
                "did not receive a valid http request" in exc_text
                or "missing connection header" in exc_text
            ):
                _log_handshake_reject_summary()
                return False

        return True


def _configure_websocket_logging():
    """Attach filter to websockets loggers to reduce noisy handshake tracebacks."""
    noise_filter = _WebSocketHandshakeNoiseFilter()

    for logger_name in ("websockets.server", "websockets.asyncio.server"):
        ws_logger = logging.getLogger(logger_name)

        if not any(isinstance(existing, _WebSocketHandshakeNoiseFilter) for existing in ws_logger.filters):
            ws_logger.addFilter(noise_filter)


_configure_websocket_logging()

def authenticate_token(token):
    """Validate client token against DB-backed token store."""
    from security.token_store import verify_token
    from Server import app

    with app.app_context():
        rec, reason = verify_token(token)

    return bool(rec)


def authenticate_token_with_policy(token, *, client_id=None, client_ip=None, required_scope=None):
    """Validate token against DB-backed token store."""
    from security.token_store import verify_token
    from Server import app

    with app.app_context():
        rec, reason = verify_token(
            token,
        )

    if rec:
        return {
            'ok': True,
            'name': rec.name,
            'client_type': rec.client_type,
            'token_id': rec.id,
            'source': 'db',
        }

    return {'ok': False, 'reason': reason or 'authentication_failed'}


def _security_log(event, **kwargs):
    """Best-effort security event logging."""
    try:
        payload = {'event': event}
        payload.update(kwargs)
        sec_logger.warning(json.dumps(payload))
    except Exception:
        try:
            print(f"[SECURITY] {event}: {kwargs}")
        except Exception:
            pass

def get_ws_client_ip(ws):
    """Resolve client IP for WebSocket connections using forwarded headers when available."""
    try:
        xff = ws.request_headers.get('X-Forwarded-For') or ws.request_headers.get('X-Real-IP')
        if xff:
            return xff.split(',')[0].strip()
    except Exception:
        pass
    return ws.remote_address[0] if ws.remote_address else "unknown"

def check_rate_limit(client_ip):
    """Simple rate limiting check"""
    # Rate limiting disabled for normal users
    # current_time = time.time()
    # minute_key = int(current_time // 60)
    # 
    # if client_ip not in client_request_counts:
    #     client_request_counts[client_ip] = {}
    # 
    # if minute_key not in client_request_counts[client_ip]:
    #     client_request_counts[client_ip][minute_key] = 0
    # 
    # client_request_counts[client_ip][minute_key] += 1
    # 
    # # Clean old entries
    # old_keys = [k for k in client_request_counts[client_ip].keys() if k < minute_key - 1]
    # for k in old_keys:
    #     del client_request_counts[client_ip][k]
    # 
    # return client_request_counts[client_ip][minute_key] <= REQUEST_LIMIT_PER_MINUTE
    
    return True  # Allow all requests for normal users

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
        self._lock = threading.Lock()

    def add_client(self, client_id, ws):
        with self._lock:
            self.clients[client_id] = Client(client_id, ws)

    def try_add_client(self, client_id, ws):
        """Atomically add client only if not currently connected."""
        with self._lock:
            if client_id in self.clients:
                return False
            self.clients[client_id] = Client(client_id, ws)
            return True

    def remove_client(self, client_id):
        with self._lock:
            self.clients.pop(client_id, None)

    def command(self, client_id, function_name, args=None, kwargs=None):
        """Send command to client using thread-safe asyncio.run_coroutine_threadsafe"""
        global ws_event_loop
        if client_id not in self.clients:
            raise Exception(f"Client '{client_id}' not found")
        
        if ws_event_loop is None:
            raise Exception("WebSocket event loop not initialized")
        
        # Use run_coroutine_threadsafe to safely execute async code from another thread
        coroutine = self.clients[client_id].execute(function_name, args, kwargs)
        future = asyncio.run_coroutine_threadsafe(coroutine, ws_event_loop)
        
        try:
            # Wait for result with timeout
            result = future.result(timeout=5)
            return result
        except Exception as e:
            raise Exception(f"Command execution failed: {str(e)}")

    def get_client(self, client_id):
        with self._lock:
            return self.clients.get(client_id)

# Global client manager instance
client_manager = ClientManager()

async def telescope_heartbeat(client_id, client_name, telescope_id, ws):
    """
    Send periodic heartbeat pings to telescope and update last_seen in database.
    Runs every 30 seconds.
    """
    while True:
        try:
            await asyncio.sleep(30)  # Wait 30 seconds between pings

            try:
                pong_waiter = ws.ping()
                await asyncio.wait_for(pong_waiter, timeout=10)

                # Update last_seen in database on successful ping/pong
                from models.tables import Telescope
                from Server import app
                with app.app_context():
                    result = Telescope.update_last_seen(telescope_id)
                    if result.get('status') == 'success':
                        # Only log occasionally to avoid spam (every 5 minutes)
                        if int(time.time()) % 300 < 30:  # Log once every 10 pings
                            print(f"[Heartbeat] {client_name} alive (last_seen updated)")

            except websockets.exceptions.ConnectionClosed:
                print(f"[Heartbeat] {client_name} connection closed, stopping heartbeat")
                break
            except Exception as e:
                print(f"[Heartbeat] Error pinging {client_name}: {e}")
                break
                
        except asyncio.CancelledError:
            print(f"[Heartbeat] Stopped for {client_name}")
            break
        except Exception as e:
            print(f"[Heartbeat] Unexpected error for {client_name}: {e}")
            break

async def handle_client(ws):
    client_ip = get_ws_client_ip(ws)
    
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
        
        auth_result = authenticate_token_with_policy(
            token,
            client_id=client_id,
            client_ip=client_ip,
        )

        if not token or not auth_result.get('ok'):
            reason = auth_result.get('reason', 'authentication_failed')
            _security_log('ws_command_auth_failed', ip=client_ip, client_id=client_id, reason=reason)
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
    
    # Authentication successful; refuse silent replacement of existing client_id
    if not client_manager.try_add_client(client_id, ws):
        _security_log('ws_command_client_id_already_connected', ip=client_ip, client_id=client_id)
        await ws.close(code=4009, reason='Client ID already connected')
        return

    client_type = auth_result.get('client_type', 'unknown')
    client_name = auth_result.get('name', client_id)
    print(f"[+] {client_name} ({client_type}) connected from {client_ip}")
    _security_log('ws_command_connected', ip=client_ip, client_id=client_id, client_name=client_name, client_type=client_type, token_source=auth_result.get('source'))
    
    # Handle telescope database operations
    if client_type == 'telescope':
        try:
            from models.tables import Telescope
            from Server import app
            with app.app_context():
                from app.db import db
                # Check if telescope exists in database by name
                existing = Telescope.get_telescope_by_id(client_name)

                if not existing:
                    # If an old token-based record exists, migrate it to the name
                    legacy = db.session.query(Telescope).filter_by(telescope_id=token).first()
                    if legacy:
                        legacy.telescope_id = client_name
                        legacy.type = client_type
                        if client_ip and client_ip != 'unknown':
                            legacy.ip_address = client_ip
                        legacy.last_seen = time.time()
                        db.session.commit()
                        print(f"[DB] Migrated telescope ID to '{client_name}'")
                    else:
                        # Auto-add telescope to database
                        result = Telescope.add_telescope(
                            telescope_id=client_name,
                            telescope_type=client_type,
                            ip_address=client_ip if client_ip != 'unknown' else None,
                            last_seen=time.time()
                        )
                        if result['status'] == 'success':
                            print(f"[DB] Auto-added telescope '{client_name}' to database (ID: {result.get('id')})")
                        else:
                            print(f"[DB] Failed to auto-add telescope: {result['message']}")
                else:
                    # Update existing telescope
                    Telescope.update_last_seen(client_name)
                    if client_ip and client_ip != 'unknown':
                        Telescope.update_ip_address(client_name, client_ip)
                    record = db.session.query(Telescope).filter_by(telescope_id=client_name).first()
                    if record and record.type != client_type:
                        record.type = client_type
                        db.session.commit()
                    print(f"[DB] Updated telescope '{client_name}' in database")
        except Exception as e:
            print(f"[WARNING] Could not update telescope database: {e}")
    
    # Start heartbeat task for telescopes
    heartbeat_task = None
    if client_type == 'telescope':
        heartbeat_task = asyncio.create_task(
            telescope_heartbeat(client_id, client_name, client_name, ws)
        )
        heartbeat_tasks[client_id] = heartbeat_task

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
        # Cancel heartbeat task if it exists
        if client_id in heartbeat_tasks:
            heartbeat_tasks[client_id].cancel()
            del heartbeat_tasks[client_id]
        client_manager.remove_client(client_id)
        _security_log('ws_command_disconnected', ip=client_ip, client_id=client_id)

# WebSocket handler for live view frames from client
async def handle_liveview_client(ws):
    client_ip = get_ws_client_ip(ws)
    
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
        
        auth_result = authenticate_token_with_policy(
            token,
            client_id=client_id,
            client_ip=client_ip,
        )

        if not token or not auth_result.get('ok'):
            reason = auth_result.get('reason', 'authentication_failed')
            _security_log('ws_liveview_auth_failed', ip=client_ip, client_id=client_id, reason=reason)
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
    client_type = auth_result.get('client_type', 'unknown')
    client_name = auth_result.get('name', client_id)
    print(f"[LiveView] {client_name} ({client_type}) connected from {client_ip}")
    _security_log('ws_liveview_connected', ip=client_ip, client_id=client_id, client_name=client_name, client_type=client_type, token_source=auth_result.get('source'))
    
    # Handle telescope database operations
    if client_type == 'telescope':
        try:
            from models.tables import Telescope
            from Server import app
            with app.app_context():
                from app.db import db
                # Check if telescope exists in database by name
                existing = Telescope.get_telescope_by_id(client_name)

                if not existing:
                    legacy = db.session.query(Telescope).filter_by(telescope_id=token).first()
                    if legacy:
                        legacy.telescope_id = client_name
                        legacy.type = client_type
                        if client_ip and client_ip != 'unknown':
                            legacy.ip_address = client_ip
                        legacy.last_seen = time.time()
                        db.session.commit()
                        print(f"[DB] Migrated telescope ID to '{client_name}'")
                    else:
                        # Auto-add telescope to database
                        result = Telescope.add_telescope(
                            telescope_id=client_name,
                            telescope_type=client_type,
                            ip_address=client_ip if client_ip != 'unknown' else None,
                            last_seen=time.time()
                        )
                        if result['status'] == 'success':
                            print(f"[DB] Auto-added telescope '{client_name}' to database (ID: {result.get('id')})")
                else:
                    # Update existing telescope
                    Telescope.update_last_seen(client_name)
                    if client_ip and client_ip != 'unknown':
                        Telescope.update_ip_address(client_name, client_ip)
                    record = db.session.query(Telescope).filter_by(telescope_id=client_name).first()
                    if record and record.type != client_type:
                        record.type = client_type
                        db.session.commit()
        except Exception as e:
            print(f"[WARNING] Could not update telescope database: {e}")
    
    # Start heartbeat task for telescopes
    liveview_heartbeat_task = None
    if client_type == 'telescope':
        liveview_client_id = f"{client_id}_liveview"
        liveview_heartbeat_task = asyncio.create_task(
            telescope_heartbeat(liveview_client_id, f"{client_name} (LiveView)", client_name, ws)
        )
        heartbeat_tasks[liveview_client_id] = liveview_heartbeat_task
    
    try:
        while True:
            try:
                message = await ws.recv()
                latest_frames[client_id] = message
                now = time.time()
                # Only log every 2 seconds per client
                if (client_id not in last_frame_log_time) or (now - last_frame_log_time[client_id] > 2):
                    # print(f"[LiveView] Received frame from {client_name}, size: {len(message)} bytes")
                    last_frame_log_time[client_id] = now
            except websockets.exceptions.ConnectionClosed:
                print(f"[LiveView] {client_name} disconnected from live view.")
                break
            except websockets.exceptions.ConnectionClosedError as e:
                # Check if it's a frame size error
                if "payload length" in str(e) and "max_size" in str(e):
                    print(f"[LiveView] Frame too large from {client_name}, skipping and continuing...")
                    continue  # Skip this frame and continue receiving
                else:
                    print(f"[LiveView] Connection closed for {client_name}: {e}")
                    break
            except websockets.exceptions.PayloadTooBig:
                print(f"[LiveView] Frame too large from {client_name}, skipping and continuing...")
                continue  # Skip this frame and continue receiving
            except Exception as e:
                # Log the error but continue trying to receive frames
                print(f"[LiveView] Error receiving frame from {client_name}: {e}")
                # Small delay to prevent tight error loops
                await asyncio.sleep(0.1)
    except Exception as e:
        print(f"[LiveView] Error in connection: {e}")
    finally:
        # Cancel heartbeat task if it exists
        if client_type == 'telescope':
            liveview_client_id = f"{client_id}_liveview"
            if liveview_client_id in heartbeat_tasks:
                heartbeat_tasks[liveview_client_id].cancel()
                del heartbeat_tasks[liveview_client_id]
        latest_frames.pop(client_id, None)
        last_frame_log_time.pop(client_id, None)
        _security_log('ws_liveview_disconnected', ip=client_ip, client_id=client_id)


def _extract_api_token_from_request():
    """Extract API token from header or JSON body."""
    auth_header = (request.headers.get('Authorization') or '').strip()
    if auth_header.lower().startswith('bearer '):
        return auth_header[7:].strip()

    header_token = (request.headers.get('X-API-Token') or '').strip()
    if header_token:
        return header_token

    try:
        data = request.get_json(silent=True) or {}
        body_token = (data.get('token') or '').strip()
        if body_token:
            return body_token
    except Exception:
        pass

    return None


def _is_loopback_request():
    """Allow internal localhost requests without token for backwards compatibility."""
    try:
        host = (request.remote_addr or '').strip()
        return host in ('127.0.0.1', '::1', 'localhost')
    except Exception:
        return False


def _authorize_send_command(client_id):
    """Authorize /sendCommand access.

    Allowed when:
    - authenticated admin user, OR
    - loopback request, OR
    - valid API token with send_command scope.
    """
    try:
        if current_user and getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'is_admin', False):
            return True, 'admin'
    except Exception:
        pass

    if _is_loopback_request():
        return True, 'loopback'

    token = _extract_api_token_from_request()
    if token:
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        auth_result = authenticate_token_with_policy(
            token,
            client_id=client_id,
            client_ip=(client_ip.split(',')[0].strip() if client_ip else 'unknown'),
        )
        if auth_result.get('ok'):
            return True, auth_result.get('source', 'token')

    return False, 'forbidden'

def save_latest_frame(client_id):
    frame = latest_frames.get(client_id)
    if frame:
        try:
            tmp_dir = tempfile.gettempdir()
            file_path = os.path.join(tmp_dir, f"{client_id}_latest.jpg")
            with open(file_path, "wb") as f:
                f.write(frame)
            # print(f"[DEBUG] Saved {file_path}")
        except Exception as e:
            print(f"[DEBUG] Failed to save frame for {client_id}: {e}")

# Start WebSocket Server in Background
def start_ws_server():
    global ws_event_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ws_event_loop = loop  # Store reference for thread-safe operations
    async def run_server():
        try:
            async with websockets.serve(
                handle_client,
                WS_IP,
                WS_PORT,
                ping_interval=WS_PING_INTERVAL,
                ping_timeout=WS_PING_TIMEOUT
            ):
                # print(f"Command WebSocket server running locally at ws://{WS_IP}:{WS_PORT} \n")
                # print(f"Public access via: wss://ws.telescopes.dev \n")
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
            async with websockets.serve(
                handle_liveview_client,
                WS_IP,
                LIVEVIEW_WS_PORT,
                max_size=2*1024*1024,
                ping_interval=WS_PING_INTERVAL,
                ping_timeout=WS_PING_TIMEOUT
            ):
                # print(f"LiveView WebSocket server running locally at ws://{WS_IP}:{LIVEVIEW_WS_PORT}")
                # print(f"Public access via: wss://liveview.telescopes.dev")
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
    kwargs = data.get('kwargs', {})  # Extract kwargs from request

    allowed, auth_source = _authorize_send_command(client_id)
    if not allowed:
        _security_log(
            'send_command_denied',
            client_id=client_id,
            command=command,
            ip=request.headers.get('X-Forwarded-For', request.remote_addr),
        )
        return jsonify({"status": "error", "error": "Unauthorized"}), 403

    _security_log(
        'send_command_allowed',
        auth_source=auth_source,
        client_id=client_id,
        command=command,
        ip=request.headers.get('X-Forwarded-For', request.remote_addr),
    )

    try:
        result = client_manager.command(client_id, command, args, kwargs)
        return jsonify({"status": "success", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


def admin_disconnect_ws_client_handler(client_id):
    """Admin override: disconnect an active websocket command client by client_id."""
    try:
        if not current_user or not getattr(current_user, 'is_authenticated', False) or not getattr(current_user, 'is_admin', False):
            return jsonify({'status': 'error', 'error': 'Admin access required'}), 403
    except Exception:
        return jsonify({'status': 'error', 'error': 'Admin access required'}), 403

    existing = client_manager.get_client(client_id)
    if not existing:
        return jsonify({'status': 'error', 'error': 'Client not connected'}), 404

    global ws_event_loop
    if ws_event_loop is None:
        return jsonify({'status': 'error', 'error': 'WebSocket event loop not initialized'}), 500

    try:
        fut = asyncio.run_coroutine_threadsafe(
            existing.ws.close(code=4010, reason='Admin override disconnect'),
            ws_event_loop,
        )
        fut.result(timeout=5)
        client_manager.remove_client(client_id)
        _security_log('ws_command_admin_disconnect', client_id=client_id, by=getattr(current_user, 'id', None))
        return jsonify({'status': 'success', 'message': f"Disconnected '{client_id}'"})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

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
    
    token = data.get('token') or generate_token()
    client_type = data.get('client_type', 'observer')  # telescope, observer
    name = data.get('name', 'Unknown Client')

    # Persist token to DB-backed telescope token store
    try:
        from security.token_store import upsert_raw_token_record
        from Server import app

        with app.app_context():
            upsert_raw_token_record(
                token,
                name=name,
                client_type=client_type,
            )
    except Exception as e:
        print(f"[WARNING] Failed to persist API token to DB: {e}")
    
    print(f"[ADMIN] Added API token for {name} ({client_type})")
    
    return jsonify({
        "token": token,
        "client_type": client_type,
        "name": name,
        "message": "Token added successfully"
    })
