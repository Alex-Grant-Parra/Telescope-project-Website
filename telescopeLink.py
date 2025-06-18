import requests
import ujson


flaskLinkIp = "172.25.199.161"
url = f"http://{flaskLinkIp}:25566/sendCommand" # Url for sending flask server commands

# Example
# payload = {"client_id": client_id, "command": "add", "args": [5, 7]}
# response = requests.post(url, json=payload).text
# print(response)

import requests  


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