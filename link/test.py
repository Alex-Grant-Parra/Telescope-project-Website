import requests  

client_id = "pi-001"
WSL_IP = "172.25.199.161"
url = f"http://{WSL_IP}:25566/sendCommand"
payload = {"client_id": client_id, "command": "get_temperature"}

print(f"Sending request to {url}...")
response = requests.post(url, json=payload)

print("Raw Response:", response.text)

try:
    print("Parsed JSON Response:", response.json())
except requests.exceptions.JSONDecodeError:
    print("Error: Response is not valid JSON.")
