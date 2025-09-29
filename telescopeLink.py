import requests
import ujson
import asyncio
import websockets
import subprocess
from WebsocketServer import clients
from time import sleep
from PIL import Image
import io
import os
import yaml

url = f"https://telescopes.dev/sendCommand" # Url for sending flask server commands

# Example
# payload = {"client_id": client_id, "command": "add", "args": [5, 7]}
# response = requests.post(url, json=payload).text
# print(response)

# clientIndex = 0
# client_id = None

# def getClientID():
#     global client_id
#     if clients:
#         client_id = clients[clientIndex]
#         print("Updated client_id:")
#     else:
#         print("No clients to update with")

client_id = "pi-001"

def load_api_token():
    """Load API token from api_tokens.json file"""
    try:
        with open("api_tokens.json", "r") as f:
            tokens = ujson.load(f)
            # Return the first token found (assumes telescope has one token)
            for token, info in tokens.items():
                if info.get('client_type') == 'telescope':
                    return token
            # If no telescope token, return any token
            return list(tokens.keys())[0] if tokens else None
    except Exception as e:
        print(f"Warning: Could not load API token: {e}")
        return None

class Cameralink:

    # @staticmethod
    def getSettings():
        payload = {"client_id": client_id, "command": "getCameraChoices"}
        response = requests.post(url, json=payload).text 
        
        data = ujson.loads(response) 
        extracted_data = data["result"] 
        
        return extracted_data  
    
    # @staticmethod
    def setSettings(args):
        payload = {"client_id": client_id, "command": "setCameraSetting", "args": args}
        response = requests.post(url, json=payload).text

        data = ujson.loads(response)
        extracted_data = data["result"] 
        
        return extracted_data  
    
    def capturePhoto(currentid):
        payload = {"client_id": client_id, "command": "capturePhoto", "args": currentid}
        response = requests.post(url, json=payload).text

        data = ujson.loads(response)

        print(data)
        
        return data

    def start_liveview_client(server_ip=None, client_id=None):
        # Maximum frame size (2MB - small buffer for safety)
        MAX_FRAME_SIZE = 2 * 1024 * 1024 - 10240  # 2MB minus 10KB buffer
        
        def compress_frame_if_needed(frame_data):
            """Compress frame if it's too large, return compressed data or None if should skip"""
            if len(frame_data) <= MAX_FRAME_SIZE:
                return frame_data
                
            try:
                # Try to compress the JPEG frame
                image = Image.open(io.BytesIO(frame_data))
                
                # Progressive quality reduction until under size limit
                for quality in [85, 70, 55, 40, 25]:
                    output = io.BytesIO()
                    image.save(output, format='JPEG', quality=quality, optimize=True)
                    compressed_data = output.getvalue()
                    
                    if len(compressed_data) <= MAX_FRAME_SIZE:
                        print(f"[LiveView] Compressed frame from {len(frame_data)} to {len(compressed_data)} bytes (quality {quality})")
                        return compressed_data
                
                # If still too large even at lowest quality, skip frame
                print(f"[LiveView] Frame too large ({len(frame_data)} bytes), skipping...")
                return None
                
            except Exception as e:
                print(f"[LiveView] Error compressing frame: {e}, skipping...")
                return None
        
        async def send_frames():
            # Load API token
            api_token = load_api_token()
            if not api_token:
                print("[LiveView] Error: No API token found. Please configure api_tokens.json")
                return
            
            # Use new WSS endpoint through Cloudflare Tunnel
            uri = "wss://liveview.telescopes.dev"
            async with websockets.connect(uri, max_size=2*1024*1024) as ws:
                # Send authentication data
                auth_data = {
                    "token": api_token,
                    "client_id": client_id
                }
                await ws.send(ujson.dumps(auth_data))
                
                # Use gphoto2 to capture preview frames
                proc = subprocess.Popen([
                    "gphoto2", "--capture-movie", "--stdout"
                ], stdout=subprocess.PIPE)
                
                frame_buffer = b""
                try:
                    while True:
                        # Read data in chunks
                        chunk = proc.stdout.read(1024*32)  # 32KB chunks
                        if not chunk:
                            break
                            
                        frame_buffer += chunk
                        
                        # Look for JPEG end marker (FF D9) to detect complete frames
                        while b'\xff\xd9' in frame_buffer:
                            # Find the end of current JPEG
                            end_pos = frame_buffer.find(b'\xff\xd9') + 2
                            complete_frame = frame_buffer[:end_pos]
                            frame_buffer = frame_buffer[end_pos:]
                            
                            # Check and compress frame if needed
                            processed_frame = compress_frame_if_needed(complete_frame)
                            if processed_frame:
                                try:
                                    await ws.send(processed_frame)
                                except websockets.exceptions.ConnectionClosed:
                                    print("[LiveView] Connection closed during frame send")
                                    return
                                except Exception as e:
                                    print(f"[LiveView] Error sending frame: {e}")
                                    # Continue trying to send other frames
                            # If processed_frame is None, frame was skipped due to size
                            
                finally:
                    proc.terminate()
        asyncio.run(send_frames())

    @staticmethod
    def startLiveView():
        print("Starting Live View from telescopeLink.py")
        payload = {"client_id": client_id, "command": "startLiveView"}
        response = requests.post(url, json=payload).text

        data = ujson.loads(response)
        extracted_data = data["result"] 
        
        return extracted_data
    
    @staticmethod
    def stopLiveView():
        print("Stopping Live View from telescopeLink.py")
        payload = {"client_id": client_id, "command": "stopLiveView"}
        response = requests.post(url, json=payload).text

        data = ujson.loads(response)
        extracted_data = data["result"] 
        
        return extracted_data  