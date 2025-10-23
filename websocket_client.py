import asyncio
import websockets
import ujson as json  # Using ujson for faster serialization
import time
import subprocess
import sys
import re
import signal
import os
from datetime import datetime
from function_handlers import function_map, is_liveview_enabled

CLIENT_ID_FILE = "client_id.json"
CONFIG_FILE = "client_config.json"
SERVER_URI = "wss://ws.telescopes.dev"  # Command websocket
LIVEVIEW_URI = "wss://liveview.telescopes.dev"  # Liveview websocket
SERVER_HTTP_URL = "https://telescopes.dev"
CLIENT_ID = "pi-001"

def load_config():
    """Load client configuration including API token"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[config] Error loading config: {e}")
    
    # Return default config
    return {
        "client_id": CLIENT_ID,
        "server_uri": SERVER_URI,
        "liveview_uri": LIVEVIEW_URI,
        "server_http_url": SERVER_HTTP_URL,
        "api_token": None
    }

def save_config(config):
    """Save client configuration"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"[config] Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"[config] Error saving config: {e}")

# Load configuration
config = load_config()
CLIENT_ID = config.get("client_id", CLIENT_ID)
SERVER_URI = config.get("server_uri", SERVER_URI)
LIVEVIEW_URI = config.get("liveview_uri", LIVEVIEW_URI)
SERVER_HTTP_URL = config.get("server_http_url", SERVER_HTTP_URL)
API_TOKEN = config.get("api_token")

async def authenticate_with_server(ws):
    """Send authentication message to server"""
    if not API_TOKEN:
        print("[auth] ERROR: No API token configured!")
        print("[auth] Please set your API token in client_config.json")
        print("[auth] Example config:")
        print(json.dumps({
            "client_id": CLIENT_ID,
            "server_uri": SERVER_URI,
            "api_token": "your-token-here"
        }, indent=2))
        raise Exception("No API token configured")
    
    auth_message = {
        "token": API_TOKEN,
        "client_id": CLIENT_ID
    }
    
    await ws.send(json.dumps(auth_message))
    print(f"[auth] Sent authentication for client: {CLIENT_ID}")

async def handle_server(ws):
    """Handle incoming WebSocket messages and execute mapped functions"""
    # Send authentication as first message
    await authenticate_with_server(ws)
    
    last_message_time = time.time()
    
    try:
        async for message in ws:
            try:
                last_message_time = time.time()
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
                error_response = json.dumps({"error": str(e)})
                try:
                    await ws.send(error_response)
                except:
                    print(f"[handle_server] Failed to send error response: {e}")
                    raise
    except Exception as e:
        error_type = type(e).__name__
        connection_duration = time.time() - last_message_time
        print(f"[handle_server] Connection ended at {datetime.now()}: {error_type} - {str(e)}")
        print(f"[handle_server] Connection was active for {connection_duration:.1f} seconds since last message")
        raise

async def run_client():
    """Run the main WebSocket client with automatic reconnection"""
    
    while True:  # Outer reconnection loop
        connection_start_time = time.time()
        ws = None
        try:
            print(f"[run_client] Connecting to {SERVER_URI} at {datetime.now()}...")
            ws = await websockets.connect(SERVER_URI, ping_interval=20, ping_timeout=10)
            print(f"[{CLIENT_ID}] Connected to {SERVER_URI} at {datetime.now()}")
            await handle_server(ws)
                
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            connection_duration = time.time() - connection_start_time
            
            # Provide more specific error information but suppress verbose details
            if 'ConnectionClosed' in error_type or 'ConnectionClosedError' in error_type:
                print(f"[run_client] WebSocket connection closed at {datetime.now()}")
            elif 'ConnectionRefused' in error_type:
                print(f"[run_client] Server appears to be down or unreachable at {datetime.now()}")
            elif 'timeout' in error_msg.lower():
                print(f"[run_client] Connection timeout at {datetime.now()}")
            elif 'authentication' in error_msg.lower() or 'unauthorized' in error_msg.lower():
                print(f"[run_client] Authentication failed at {datetime.now()}")
            elif 'ssl' in error_msg.lower() or 'certificate' in error_msg.lower():
                print(f"[run_client] SSL/TLS error at {datetime.now()}")
            elif 'network' in error_msg.lower() or 'unreachable' in error_msg.lower():
                print(f"[run_client] Network error at {datetime.now()}")
            else:
                print(f"[run_client] Connection lost at {datetime.now()}: {error_type}")
            
            print(f"[run_client] Connection lasted {connection_duration:.1f} seconds")
            print(f"[run_client] Reconnecting in 5 seconds...")
            
        finally:
            # Ensure proper cleanup
            if ws and ws.close_code is None:
                try:
                    await asyncio.wait_for(ws.close(), timeout=2.0)
                except:
                    pass
        
        # Wait before reconnecting
        await asyncio.sleep(5)

async def authenticate_liveview(ws):
    """Send authentication message to liveview server"""
    if not API_TOKEN:
        raise Exception("No API token configured for liveview")
    
    auth_message = {
        "token": API_TOKEN,
        "client_id": CLIENT_ID
    }
    
    await ws.send(json.dumps(auth_message))
    print(f"[liveview] Sent authentication for client: {CLIENT_ID}")

async def send_frames():
    """Send live camera frames via WebSocket with automatic reconnection"""
    JPEG_START = b'\xff\xd8'
    JPEG_END = b'\xff\xd9'
    proc = None
    last_frame_time = 0
    frame_interval = 1 / 10  # 10 FPS

    while True:  # Outer reconnection loop
        connection_start_time = time.time()
        ws = None
        try:
            print(f"[send_frames] Connecting to {LIVEVIEW_URI} at {datetime.now()}...")
            ws = await websockets.connect(LIVEVIEW_URI, max_size=2*1024*1024, ping_interval=20, ping_timeout=10)
            print(f"[send_frames] Connected successfully at {datetime.now()}")
            # Send authentication as first message
            await authenticate_liveview(ws)
            
            while True:
                if not is_liveview_enabled():
                    await asyncio.sleep(0.2)
                    continue
                
                # Check if WebSocket is still open
                if ws.close_code is not None:
                    connection_duration = time.time() - connection_start_time
                    print(f"[send_frames] WebSocket closed silently at {datetime.now()}")
                    print(f"[send_frames] Connection lasted {connection_duration:.1f} seconds")
                    print(f"[send_frames] Close code: {ws.close_code}")
                    break
                
                # Start camera capture process
                if proc is None or proc.poll() is not None:
                    if proc is not None:
                        try:
                            proc.terminate()
                            proc.wait(timeout=2)
                        except:
                            pass
                    
                    try:
                        proc = subprocess.Popen([
                            "gphoto2", "--capture-movie", "--stdout"
                        ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    except Exception as proc_error:
                        print(f"[send_frames] Failed to start gphoto2: {proc_error}")
                        await asyncio.sleep(1)
                        continue
                
                buffer = b''
                try:
                    while is_liveview_enabled() and ws.close_code is None:
                        try:
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
                                        try:
                                            await asyncio.wait_for(ws.send(jpeg), timeout=1.0)
                                            last_frame_time = now
                                        except (websockets.exceptions.ConnectionClosed, 
                                               websockets.exceptions.ConnectionClosedError,
                                               asyncio.TimeoutError) as send_error:
                                            print(f"[send_frames] WebSocket send failed: {type(send_error).__name__}")
                                            raise send_error
                                        except Exception as send_error:
                                            error_type = type(send_error).__name__
                                            error_msg = str(send_error)
                                            print(f"[send_frames] WebSocket send failed: {error_type} - {error_msg}")
                                            raise send_error
                                    buffer = buffer[end+2:]
                                else:
                                    break
                        except Exception as read_error:
                            if 'broken pipe' in str(read_error).lower():
                                print(f"[send_frames] Camera process broken pipe, restarting...")
                                break
                            else:
                                raise read_error
                        
                        if not is_liveview_enabled():
                            break
                    
                    # Clean up camera process after inner loop
                    if proc:
                        try:
                            proc.terminate()
                            proc.wait(timeout=2)
                        except:
                            pass
                        proc = None
                        
                except Exception as e:
                    print(f"[send_frames] Inner exception: {type(e).__name__} - {str(e)}")
                    # Clean up camera process on exception
                    if proc:
                        try:
                            proc.terminate()
                            proc.wait(timeout=2)
                        except:
                            pass
                        proc = None
                    raise  # Re-raise to trigger reconnection
        
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            connection_duration = time.time() - connection_start_time
            
            # Provide more specific error information but suppress the asyncio callback errors
            if 'ConnectionClosed' in error_type or 'ConnectionClosedError' in error_type:
                print(f"[send_frames] WebSocket connection closed at {datetime.now()}")
            elif 'timeout' in error_msg.lower():
                print(f"[send_frames] Connection timeout at {datetime.now()}")
            elif 'network' in error_msg.lower() or 'unreachable' in error_msg.lower():
                print(f"[send_frames] Network error at {datetime.now()}")
            elif 'ConnectionRefused' in error_type:
                print(f"[send_frames] Server refused connection at {datetime.now()}")
            else:
                print(f"[send_frames] Connection lost at {datetime.now()}: {error_type}")
            
            print(f"[send_frames] Connection lasted {connection_duration:.1f} seconds")
            print(f"[send_frames] Reconnecting in 5 seconds...")
            
        finally:
            # Ensure proper cleanup
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except:
                    try:
                        proc.kill()
                    except:
                        pass
                proc = None
            
            if ws and ws.close_code is None:
                try:
                    await asyncio.wait_for(ws.close(), timeout=2.0)
                except:
                    pass
        
        # Wait before reconnecting
        await asyncio.sleep(5)

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

def setup_client_config():
    """Interactive setup for client configuration"""
    print("=== Telescope Client Configuration Setup ===")
    print()
    
    current_config = load_config()
    
    print(f"Current client ID: {current_config.get('client_id', 'Not set')}")
    new_client_id = input("Enter client ID (press Enter to keep current): ").strip()
    if new_client_id:
        current_config['client_id'] = new_client_id
    
    print(f"Current server URI: {current_config.get('server_uri', 'Not set')}")
    new_server_uri = input("Enter server URI (press Enter to keep current): ").strip()
    if new_server_uri:
        current_config['server_uri'] = new_server_uri
    
    print(f"Current API token: {'***set***' if current_config.get('api_token') else 'Not set'}")
    new_token = input("Enter API token (press Enter to keep current): ").strip()
    if new_token:
        current_config['api_token'] = new_token
    
    save_config(current_config)
    print("\nConfiguration saved! You can now run the client.")
    return current_config

async def main():
    """Main async function that runs both WebSocket client and frame sender"""
    # Check if we need to run setup
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_client_config()
        return
    
    # Check if API token is configured
    if not API_TOKEN:
        print("ERROR: No API token configured!")
        print("Run 'python websocket_client.py setup' to configure the client.")
        print("Or manually create client_config.json with your API token.")
        return
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)
    
    try:
        # Both tasks now handle their own reconnection logic
        task1 = asyncio.create_task(run_client())
        task2 = asyncio.create_task(send_frames())
        
        # Wait for both tasks to complete (which should be never, unless interrupted)
        await asyncio.gather(task1, task2)
        
    except KeyboardInterrupt:
        print("[main] KeyboardInterrupt received, exiting and releasing camera...")
    except Exception as e:
        print(f"[main] Unexpected exception: {e}")
    finally:
        cleanup_camera()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[global] KeyboardInterrupt received, exiting and releasing camera...")
        cleanup_camera()