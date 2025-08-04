import requests
import ujson
import asyncio
import websockets
import subprocess


flaskLinkIp = "localhost"
# flaskLinkIp - "localhost" # temp
url = f"http://{flaskLinkIp}:25566/sendCommand" # Url for sending flask server commands

# Example
# payload = {"client_id": client_id, "command": "add", "args": [5, 7]}
# response = requests.post(url, json=payload).text
# print(response)


client_id = "pi-001"

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

    def start_liveview_client(server_ip, client_id):
        async def send_frames():
            uri = f"ws://{server_ip}:8002"
            async with websockets.connect(uri, max_size=2*1024*1024) as ws:
                await ws.send(client_id)
                # Use gphoto2 to capture preview frames
                proc = subprocess.Popen([
                    "gphoto2", "--capture-movie", "--stdout"
                ], stdout=subprocess.PIPE)
                try:
                    while True:
                        # Read JPEG frame from stdout (simple chunked read)
                        frame = proc.stdout.read(1024*32)
                        if not frame:
                            break
                        await ws.send(frame)
                finally:
                    proc.terminate()
        asyncio.run(send_frames())

    def startLiveView():
        payload = {"client_id": client_id, "command": "startLiveView"}
        response = requests.post(url, json=payload).text

        data = ujson.loads(response)
        extracted_data = data["result"] 
        
        return extracted_data
    
    def startLiveView():
        payload = {"client_id": client_id, "command": "stopLiveView"}
        response = requests.post(url, json=payload).text

        data = ujson.loads(response)
        extracted_data = data["result"] 
        
        return extracted_data  