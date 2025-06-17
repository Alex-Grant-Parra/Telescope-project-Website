from flask import Flask, request, jsonify
import asyncio
import threading
import websockets
import ujson as json  # Using ujson for faster serialization
import uuid

FLASK_IP = "0.0.0.0"
FLASK_PORT = 25566
WS_IP = "172.25.199.161"
WS_PORT = 8001

app = Flask(__name__)
pending = {}

class Client:
    def __init__(self, client_id, ws):
        self.client_id = client_id
        self.ws = ws

    async def execute(self, function_name, args=None, kwargs=None):
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        message_id = str(uuid.uuid4())
        message = json.dumps({
            "type": "call",
            "function": function_name,
            "args": args,
            "kwargs": kwargs,
            "id": message_id
        })

        future = asyncio.get_event_loop().create_future()
        pending[message_id] = future
        await self.ws.send(message)

        try:
            response = await asyncio.wait_for(future, timeout=3)  # Reduced timeout for faster responses
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
    print(f"[+] {client_id} connected. Stored clients: {client_manager.clients.keys()}")

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
        result = asyncio.run(client_manager.command(client_id, command, args))  # Ensure a fresh event loop
        return jsonify({"status": "success", "result": result})
    except Exception as e:
        print(f"Error executing command: {str(e)}")  # Debugging output
        return jsonify({"status": "error", "error": str(e)}), 500


def start_ws_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run_server():
        async with websockets.serve(handle_client, WS_IP, WS_PORT):
            print(f"WebSocket server running at ws://{WS_IP}:{WS_PORT}")
            await asyncio.Future()

    loop.run_until_complete(run_server())
    loop.run_forever()

if __name__ == '__main__':
    threading.Thread(target=start_ws_server, daemon=True).start()
    print(f"Starting Flask server at http://{FLASK_IP}:{FLASK_PORT}")
    app.run(host=FLASK_IP, port=FLASK_PORT)
