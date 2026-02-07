import requests
import ujson
import asyncio
import websockets
import subprocess
import os
from flask import session, has_request_context
from app.WebsocketServer import clients
from time import sleep
from PIL import Image
import io

domain = os.getenv("APP_DOMAIN", "telescopes.dev")
url = f"https://{domain}/sendCommand"  # Endpoint for sending flask server commands

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

def load_api_token():
    """Load API token from api_tokens.json file"""
    try:
        with open("security/api_tokens.json", "r") as f:
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

class Telescope:
    """Represents a single telescope (client) identified by client_id."""
    def __init__(self, client_id: str):
        if not client_id:
            raise ValueError("Telescope requires a valid client_id")
        self.client_id = client_id
        self.camera = CameraController(self)
        self.motor = MotorController(self)

    def send_command(self, command: str, args=None, kwargs=None):
        payload = {"client_id": self.client_id, "command": command}
        if args is not None:
            payload["args"] = args
        if kwargs is not None:
            payload["kwargs"] = kwargs
        try:
            resp_text = requests.post(url, json=payload, timeout=8).text
            data = ujson.loads(resp_text)
            return data.get("result", data)
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def resolve_client_id(provided_id=None):
        if provided_id:
            return provided_id
        try:
            if has_request_context():
                selected = session.get('selected_telescope') or {}
                sel_id = selected.get('telescope_id')
                if sel_id:
                    return sel_id
        except Exception:
            pass
        return None

    @classmethod
    def from_session(cls):
        cid = cls.resolve_client_id()
        if not cid:
            raise ValueError("No selected telescope in session")
        return cls(cid)


class CameraController:
    def __init__(self, telescope: 'Telescope'):
        self.telescope = telescope

    def get_settings(self):
        return self.telescope.send_command("getCameraChoices")

    def set_settings(self, args):
        return self.telescope.send_command("setCameraSetting", args)

    def capture_photo(self, current_id):
        return self.telescope.send_command("capturePhoto", current_id)

    def start_live_view(self):
        return self.telescope.send_command("startLiveView")

    def stop_live_view(self):
        return self.telescope.send_command("stopLiveView")

    # Port of previous start_liveview_client logic as an instance method (optional use)
    def stream_live_view(self):
        MAX_FRAME_SIZE = 2 * 1024 * 1024 - 10240
        def compress_frame_if_needed(frame_data: bytes):
            if len(frame_data) <= MAX_FRAME_SIZE:
                return frame_data
            try:
                image = Image.open(io.BytesIO(frame_data))
                for quality in [85, 70, 55, 40, 25]:
                    output = io.BytesIO()
                    image.save(output, format='JPEG', quality=quality, optimize=True)
                    compressed = output.getvalue()
                    if len(compressed) <= MAX_FRAME_SIZE:
                        print(f"[LiveView] Compressed frame {len(frame_data)} -> {len(compressed)} bytes (q={quality})")
                        return compressed
                print(f"[LiveView] Frame still too large ({len(frame_data)} bytes), skipping")
                return None
            except Exception as e:
                print(f"[LiveView] Compression error: {e}")
                return None
        async def send_frames():
            api_token = load_api_token()
            if not api_token:
                print("[LiveView] No API token found")
                return
            lv_domain = os.getenv("APP_DOMAIN", "telescopes.dev")
            uri = f"wss://liveview.{lv_domain}"
            async with websockets.connect(uri, max_size=2*1024*1024) as ws:
                await ws.send(ujson.dumps({"token": api_token, "client_id": self.telescope.client_id}))
                proc = subprocess.Popen(["gphoto2", "--capture-movie", "--stdout"], stdout=subprocess.PIPE)
                frame_buffer = b""
                try:
                    while True:
                        chunk = proc.stdout.read(1024 * 32)
                        if not chunk:
                            break
                        frame_buffer += chunk
                        while b'\xff\xd9' in frame_buffer:
                            end_pos = frame_buffer.find(b'\xff\xd9') + 2
                            complete = frame_buffer[:end_pos]
                            frame_buffer = frame_buffer[end_pos:]
                            processed = compress_frame_if_needed(complete)
                            if processed:
                                try:
                                    await ws.send(processed)
                                except websockets.exceptions.ConnectionClosed:
                                    print("[LiveView] Connection closed during send")
                                    return
                                except Exception as e:
                                    print(f"[LiveView] Send error: {e}")
                finally:
                    proc.terminate()
        asyncio.run(send_frames())


class MotorController:
    def __init__(self, telescope: 'Telescope'):
        self.telescope = telescope

    def enable(self, on, motor_id="motor1"):
        """Enable/disable the stepper driver for a specific motor."""
        return self.telescope.send_command("espEnable", args=[bool(on)], kwargs={"motor_id": motor_id})

    def set_direction(self, forward, motor_id="motor1"):
        """Set motor direction: True=forward, False=reverse."""
        return self.telescope.send_command("espSetDirection", args=[bool(forward)], kwargs={"motor_id": motor_id})

    def set_speed(self, sps, motor_id="motor1"):
        """Set continuous target speed in steps/sec (does not auto-enable)."""
        return self.telescope.send_command("espSetSpeed", args=[float(sps)], kwargs={"motor_id": motor_id})

    def start(self, sps, forward=None, motor_id="motor1"):
        """Start continuous rotation at speed; optional direction; auto-enables."""
        args = [float(sps)]
        if forward is not None:
            args.append(bool(forward))
        return self.telescope.send_command("espStart", args=args, kwargs={"motor_id": motor_id})

    def move_steps(self, steps, sps=None, forward=None, motor_id="motor1"):
        """Move a finite number of steps; optional speed and direction override."""
        args = [int(steps)]
        if sps is not None:
            args.append(float(sps))
        if forward is not None:
            args.append(bool(forward))
        return self.telescope.send_command("espMoveSteps", args=args, kwargs={"motor_id": motor_id})

    def stop(self, motor_id="motor1"):
        """Stop motion and disable driver for a specific motor."""
        return self.telescope.send_command("espStop", args=[], kwargs={"motor_id": motor_id})

    def set_microsteps(self, value, motor_id="motor1"):
        """Set TMC2209 microstepping value (e.g., 16, 32) for a specific motor."""
        return self.telescope.send_command("espSetMicrosteps", args=[int(value)], kwargs={"motor_id": motor_id})

    def set_current(self, mA, motor_id="motor1"):
        """Set RMS motor current in milliamps for a specific motor."""
        return self.telescope.send_command("espSetCurrent", args=[int(mA)], kwargs={"motor_id": motor_id})

    def set_mode(self, mode, motor_id="motor1"):
        """Set chopper mode: 'stealth' or 'spread' for a specific motor."""
        return self.telescope.send_command("espSetMode", args=[str(mode)], kwargs={"motor_id": motor_id})

    def set_accel(self, sps2, motor_id="motor1"):
        """Set acceleration in steps/sec^2 for ramping for a specific motor."""
        return self.telescope.send_command("espSetAccel", args=[float(sps2)], kwargs={"motor_id": motor_id})

    def status(self, motor_id="motor1"):
        """Query ESP32 firmware status for a specific motor."""
        return self.telescope.send_command("espStatus", args=[], kwargs={"motor_id": motor_id})

    def status_all(self):
        """Query status of all motors on the ESP32."""
        return self.telescope.send_command("espStatusAll", args=[])


# Convenience helper
def current_telescope() -> Telescope:
    """Return a Telescope object for the currently selected client in session."""
    return Telescope.from_session()