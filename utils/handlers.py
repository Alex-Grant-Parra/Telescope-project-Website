import time
import requests
import os
import json
from typing import Optional, Any, Dict
from core.camera.controller import Camera # type: ignore
from core.networking.csrf import get_csrf_token, SESSION
from utils.liveview_state import load_liveview_state, save_liveview_state
from core.hardware.esp32_motor import ESP32Motor, ESP32Config, ESP32MotorArray
from utils.tracking import trackCoordinates

CONFIG_FILE = "config/client_config.json"

# Default server URL; will be overridden by config if present
SERVER_URL = "https://telescopes.dev"
try:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as cf:
            cfg = json.load(cf)
            SERVER_URL = cfg.get('server_http_url', SERVER_URL)
except Exception:
    # If the config can't be read, continue with default
    pass

# Load the live view state from file, or default to True
liveview_enabled = load_liveview_state()

def echo(message):
    return f"Echo: {message}"

def get_camera_choices():
    # Map setting names to gphoto2 config paths
    settings = {
        "shutterSpeed": "/main/capturesettings/shutterspeed",
        "iso": "/main/imgsettings/iso",
        # Add more settings as needed
    }
    choices = {}
    start = time.time()
    for label, path in settings.items():
        result = Camera.getSettingChoices(label, path)
        choices[label] = result if result else []
    print(f"get_camera_choices took {time.time() - start:.2f} seconds")
    return choices

def setCameraSetting(label, value):
    Camera.setSetting(label, value)
    return f"Set {label} to {value}"

def capturePhoto(currentid):
    files = Camera.capturePhoto(currentid=currentid) # Returns a list of two file names, one raw, one jpeg

    print(files)

    if not isinstance(files, list) or len(files) < 2:
        print("[ERROR] Camera.capturePhoto() did not return two valid files")
        return

    current_dir = os.getcwd()
    photos_dir = os.path.join(current_dir, "photos/default")

    # Ensure directory exists
    if not os.path.exists(photos_dir):
        print(f"[ERROR] Directory '{photos_dir}' does not exist.")
        return

    # Prepare file paths
    files = [os.path.join(photos_dir, file) for file in files]

    # Verify files exist
    missing_files = [file for file in files if not os.path.exists(file)]
    if missing_files:
        print(f"[ERROR] The following files are missing: {missing_files}")
        return
    
    server_url = f"{SERVER_URL}/upload"

    # Prepare file tuples with filenames and basic content-types
    def _guess_mime(path: str) -> str:
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        if ext in {"jpg", "jpeg"}:
            return "image/jpeg"
        if ext in {"png"}:
            return "image/png"
        if ext in {"gif"}:
            return "image/gif"
        if ext in {"bmp"}:
            return "image/bmp"
        if ext in {"tiff", "tif"}:
            return "image/tiff"
        if ext in {"webp"}:
            return "image/webp"
        # RAW/other
        return "application/octet-stream"

    file_data = {
        f"file{index}": (os.path.basename(file), open(file, "rb"), _guess_mime(file))
        for index, file in enumerate(files)
    }

    # Prepare headers, attach CSRF if available
    headers = {}
    data = None
    token = get_csrf_token(SERVER_URL)
    if token:
        # Send both common header variations to be safe
        headers["X-CSRF-Token"] = token
        headers["X-CSRFToken"] = token
        # Also include token as form field to support Flask-WTF style
        data = {"csrf_token": token}

    try:
        print("[DEBUG] Sending files to server...")
        response = SESSION.post(
            server_url,
            files=file_data,
            headers=headers,
            data=data,
            timeout=60,
        )
        # Try to print JSON if available, else status/text
        try:
            print("[DEBUG] Server response:", response.json())
        except ValueError:
            print(f"[DEBUG] Server response status={response.status_code}, body={response.text[:300]}")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to upload files: {e}")
    finally:
        # Ensure files are closed
        for f in file_data.values():
            f.close()

def startLiveView():
    global liveview_enabled
    liveview_enabled = True
    save_liveview_state(True)
    print("[liveview] Live view started.")
    return "Live view started"

def stopLiveView():
    global liveview_enabled
    liveview_enabled = False
    save_liveview_state(False)
    
    # Release camera viewfinder using the Camera class
    Camera.releaseViewfinder()
    
    print("[liveview] Live view stopped.")
    return "Live view stopped"

# ESP32 motor control handlers

# Global motor array instance
_MOTOR_ARRAY: Optional[ESP32MotorArray] = None

def _load_motor_config() -> list[dict]:
    """Load motor configuration from config/client_config.json"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                motor_configs = config.get('motors', [])
                if motor_configs:
                    print(f"[MOTORS] Loaded {len(motor_configs)} motor configurations from {CONFIG_FILE}")
                    return motor_configs
    except Exception as e:
        print(f"[MOTORS] Warning: Could not load motor config: {e}")
    
    # Return default configuration if none found
    print("[MOTORS] Using default single motor configuration")
    return [{"motor_id": "motor1", "port": "/dev/ttyUSB0", "baudrate": 115200, "timeout": 0.2}]

def _get_motor_array() -> ESP32MotorArray:
    global _MOTOR_ARRAY
    if _MOTOR_ARRAY is None:
        # Load motor configuration from file
        motor_configs = _load_motor_config()
        _MOTOR_ARRAY = ESP32MotorArray(motor_configs)
        print(f"[MOTORS] Initialized ESP32MotorArray with {len(_MOTOR_ARRAY.motors)} motor(s)")
        for motor in _MOTOR_ARRAY.motors:
            print(f"[MOTORS] - {motor.motor_id} on {motor.cfg.port}")
    return _MOTOR_ARRAY

def _get_motor(motor_id: str = "motor1") -> ESP32Motor:
    """Get a specific motor by ID"""
    motor_array = _get_motor_array()
    try:
        return motor_array.get_by_id(motor_id)
    except ValueError:
        # Fall back to first motor if specified motor not found
        if len(motor_array.motors) > 0:
            print(f"[MOTORS] Warning: Motor '{motor_id}' not found, using first motor '{motor_array.motors[0].motor_id}'")
            return motor_array.motors[0]
        raise RuntimeError(f"No motors available and motor '{motor_id}' not found")

def espEnable(on: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Enable/disable the stepper driver."""
    try:
        motor = _get_motor(motor_id)
        return motor.enable(bool(on))
    except Exception as e:
        return {"error": str(e)}

def espSetDirection(forward: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set motor direction: True=forward, False=reverse."""
    try:
        motor = _get_motor(motor_id)
        return motor.set_direction(bool(forward))
    except Exception as e:
        return {"error": str(e)}

def espSetSpeed(sps: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set continuous target speed in steps/sec (does not auto-enable)."""
    try:
        motor = _get_motor(motor_id)
        return motor.set_speed(float(sps))
    except Exception as e:
        return {"error": str(e)}

def espStart(sps: Any, forward: Optional[Any] = None, motor_id: str = "motor1") -> Dict[str, Any]:
    """Start continuous rotation at speed; optional direction; auto-enables."""
    try:
        motor = _get_motor(motor_id)
        fwd = None if forward is None else bool(forward)
        return motor.start(float(sps), fwd)
    except Exception as e:
        return {"error": str(e)}

def espMoveSteps(steps: Any, sps: Optional[Any] = None, forward: Optional[Any] = None, motor_id: str = "motor1") -> Dict[str, Any]:
    """Move a finite number of steps; optional speed and direction override."""
    try:
        motor = _get_motor(motor_id)
        spd = None if sps is None else float(sps)
        fwd = None if forward is None else bool(forward)
        return motor.move_steps(int(steps), spd, fwd)
    except Exception as e:
        return {"error": str(e)}

def espStop(motor_id: str = "motor1") -> Dict[str, Any]:
    """Stop motion and disable driver."""
    try:
        motor = _get_motor(motor_id)
        return motor.stop()
    except Exception as e:
        return {"error": str(e)}

def espSetMicrosteps(value: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set TMC2209 microstepping value (e.g., 16, 32)."""
    try:
        motor = _get_motor(motor_id)
        return motor.set_microsteps(int(value))
    except Exception as e:
        return {"error": str(e)}

def espSetCurrent(mA: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set RMS motor current in milliamps."""
    try:
        motor = _get_motor(motor_id)
        return motor.set_current(int(mA))
    except Exception as e:
        return {"error": str(e)}

def espSetMode(mode: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set chopper mode: 'stealth' or 'spread'."""
    try:
        motor = _get_motor(motor_id)
        return motor.set_mode(str(mode))
    except Exception as e:
        return {"error": str(e)}

def espSetAccel(sps2: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set acceleration in steps/sec^2 for ramping."""
    try:
        motor = _get_motor(motor_id)
        return motor.set_accel(float(sps2))
    except Exception as e:
        return {"error": str(e)}

def espStatus(motor_id: str = "motor1") -> Dict[str, Any]:
    """Query ESP32 firmware status."""
    try:
        motor = _get_motor(motor_id)
        return motor.status()
    except Exception as e:
        return {"error": str(e)}

def espStatusAll() -> Dict[str, Any]:
    """Query status of all motors."""
    try:
        motor_array = _get_motor_array()
        return motor_array.status_all()
    except Exception as e:
        return {"error": str(e)}

# Enhanced functions that can unpack motor_id from JSON-style arguments
def espEnableWithMotorId(*args, **kwargs) -> Dict[str, Any]:
    """Enable/disable motor - can extract motor_id from JSON arguments"""
    motor_id = "motor1"  # default
    on = False
    
    # Handle different argument patterns
    if args:
        if len(args) >= 2 and isinstance(args[1], str):
            # (on, motor_id) pattern
            on, motor_id = args[0], args[1]
        elif len(args) == 1:
            if isinstance(args[0], dict) and 'motor_id' in args[0]:
                # JSON-like dict with motor_id
                data = args[0]
                on = data.get('on', data.get('value', False))
                motor_id = data.get('motor_id', 'motor1')
            else:
                # Single value
                on = args[0]
    
    if 'motor_id' in kwargs:
        motor_id = kwargs['motor_id']
    if 'on' in kwargs:
        on = kwargs['on']
    elif 'value' in kwargs:
        on = kwargs['value']
    
    return espEnable(on, motor_id)

def espStartWithMotorId(*args, **kwargs) -> Dict[str, Any]:
    """Start motor - can extract motor_id from JSON arguments"""
    motor_id = "motor1"
    sps = 0
    forward = None
    
    # Handle different argument patterns
    if args:
        if len(args) >= 3:
            sps, forward, motor_id = args[0], args[1], args[2]
        elif len(args) == 2:
            if isinstance(args[1], str):
                # (sps, motor_id)
                sps, motor_id = args[0], args[1]
            else:
                # (sps, forward)
                sps, forward = args[0], args[1]
        elif len(args) == 1:
            if isinstance(args[0], dict):
                # JSON-like dict
                data = args[0]
                sps = data.get('sps', 0)
                forward = data.get('forward')
                motor_id = data.get('motor_id', 'motor1')
            else:
                sps = args[0]
    
    # Override with kwargs
    motor_id = kwargs.get('motor_id', motor_id)
    sps = kwargs.get('sps', sps)
    if 'forward' in kwargs:
        forward = kwargs['forward']
    
    return espStart(sps, forward, motor_id)

def espMoveStepsWithMotorId(*args, **kwargs) -> Dict[str, Any]:
    """Move steps - can extract motor_id from JSON arguments"""
    motor_id = "motor1"
    steps = 0
    sps = None
    forward = None
    
    # Handle different argument patterns
    if args:
        if len(args) >= 4:
            steps, sps, forward, motor_id = args[0], args[1], args[2], args[3]
        elif len(args) >= 2 and isinstance(args[-1], str):
            # Assume last string arg is motor_id
            if len(args) == 4:
                steps, sps, forward, motor_id = args[0], args[1], args[2], args[3]
            elif len(args) == 3:
                steps, sps, motor_id = args[0], args[1], args[2]
            elif len(args) == 2:
                steps, motor_id = args[0], args[1]
        elif len(args) == 1:
            if isinstance(args[0], dict):
                # JSON-like dict
                data = args[0]
                steps = data.get('steps', 0)
                sps = data.get('sps')
                forward = data.get('forward')
                motor_id = data.get('motor_id', 'motor1')
            else:
                steps = args[0]
        else:
            # (steps, sps, forward)
            steps = args[0]
            if len(args) > 1:
                sps = args[1]
            if len(args) > 2:
                forward = args[2]
    
    # Override with kwargs
    motor_id = kwargs.get('motor_id', motor_id)
    steps = kwargs.get('steps', steps)
    sps = kwargs.get('sps', sps)
    if 'forward' in kwargs:
        forward = kwargs['forward']
    
    return espMoveSteps(steps, sps, forward, motor_id)

def espStopWithMotorId(*args, **kwargs) -> Dict[str, Any]:
    """Stop motor - can extract motor_id from JSON arguments"""
    motor_id = "motor1"
    
    if args:
        if len(args) >= 1:
            if isinstance(args[0], dict):
                # JSON-like dict
                data = args[0]
                motor_id = data.get('motor_id', 'motor1')
            elif isinstance(args[0], str):
                motor_id = args[0]
    
    motor_id = kwargs.get('motor_id', motor_id)
    return espStop(motor_id)

# Comprehensive wrappers for common ESP32 commands with flexible JSON parameter handling
def espCommand(command_data: Dict[str, Any]) -> Dict[str, Any]:
    """Universal ESP32 command handler that can parse JSON command structures"""
    try:
        cmd_type = command_data.get('command', command_data.get('cmd', ''))
        motor_id = command_data.get('motor_id', command_data.get('motor', 'motor1'))
        
        if cmd_type == 'enable':
            value = command_data.get('value', command_data.get('on', False))
            return espEnable(value, motor_id)
        elif cmd_type == 'start':
            sps = command_data.get('sps', 0)
            forward = command_data.get('forward')
            return espStart(sps, forward, motor_id)
        elif cmd_type == 'move_steps':
            steps = command_data.get('steps', 0)
            sps = command_data.get('sps')
            forward = command_data.get('forward')
            return espMoveSteps(steps, sps, forward, motor_id)
        elif cmd_type == 'stop':
            return espStop(motor_id)
        elif cmd_type == 'set_speed':
            sps = command_data.get('sps', 0)
            return espSetSpeed(sps, motor_id)
        elif cmd_type == 'set_direction':
            forward = command_data.get('forward', True)
            return espSetDirection(forward, motor_id)
        elif cmd_type == 'set_current':
            mA = command_data.get('mA', command_data.get('current', 500))
            return espSetCurrent(mA, motor_id)
        elif cmd_type == 'set_microsteps':
            value = command_data.get('value', command_data.get('microsteps', 16))
            return espSetMicrosteps(value, motor_id)
        elif cmd_type == 'set_mode':
            mode = command_data.get('mode', 'stealth')
            return espSetMode(mode, motor_id)
        elif cmd_type == 'set_accel':
            sps2 = command_data.get('sps2', command_data.get('accel', 1000))
            return espSetAccel(sps2, motor_id)
        elif cmd_type == 'status':
            return espStatus(motor_id)
        elif cmd_type == 'status_all':
            return espStatusAll()
        else:
            return {"error": f"Unknown command: {cmd_type}"}
    except Exception as e:
        return {"error": str(e)}

# Function mapping dictionary
function_map = {
    # Degub
    "echo": echo,
    # Main track requests
    "trackCoordinates": trackCoordinates,
    "getCameraChoices": get_camera_choices,
    "setCameraSetting": setCameraSetting,
    "capturePhoto": capturePhoto,
    "startLiveView": startLiveView,
    "stopLiveView": stopLiveView,
    # ESP32 controls - original functions (backward compatibility)
    "espEnable": espEnable,
    "espSetDirection": espSetDirection,
    "espSetSpeed": espSetSpeed,
    "espStart": espStart,
    "espMoveSteps": espMoveSteps,
    "espStop": espStop,
    "espSetMicrosteps": espSetMicrosteps,
    "espSetCurrent": espSetCurrent,
    "espSetMode": espSetMode,
    "espSetAccel": espSetAccel,
    "espStatus": espStatus,
    "espStatusAll": espStatusAll,
    # Enhanced ESP32 controls with motor ID support
    "espEnableMotor": espEnableWithMotorId,
    "espStartMotor": espStartWithMotorId,
    "espMoveStepsMotor": espMoveStepsWithMotorId,
    "espStopMotor": espStopWithMotorId,
    # Universal command handler
    "espCommand": espCommand,
}

# Example usage for motor identification:
# 
# 1. WebSocket JSON commands can now include motor_id:
# {
#   "function": "espStart",
#   "args": [800, true],
#   "motor_id": "motor1"
# }
# 
# 2. Or use the universal command handler:
# {
#   "function": "espCommand",
#   "args": [{
#     "command": "start",
#     "sps": 800,
#     "forward": true,
#     "motor_id": "motor1"
#   }]
# }
# 
# 3. Enhanced motor functions accept JSON-like arguments:
# {
#   "function": "espStartMotor",
#   "args": [{
#     "sps": 800,
#     "forward": true,
#     "motor_id": "motor1"
#   }]
# }
