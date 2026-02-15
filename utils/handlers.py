import time
import requests
import os
import json
from typing import Optional, Any, Dict
from core.camera.controller import Camera # type: ignore
from core.networking.csrf import get_csrf_token, SESSION
from utils.liveview_state import load_liveview_state, save_liveview_state
from esp32.interfaceESP32 import ESP32Connection, ESP32SerialConfig
from core.hardware.tracking import trackCoordinates, stop_tracking

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

# Global ESP32 connection instance
_ESP32_CONN: Optional[ESP32Connection] = None

def _load_motor_config() -> dict:
    """Load motor configuration from config/client_config.json"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                esp32_config = config.get('esp32', {})
                if esp32_config:
                    print(f"[MOTORS] Loaded ESP32 configuration from {CONFIG_FILE}")
                    return esp32_config
    except Exception as e:
        print(f"[MOTORS] Warning: Could not load ESP32 config: {e}")
    
    # Return default configuration if none found
    print("[MOTORS] Using default ESP32 configuration")
    return {
        "port": "/dev/ttyUSB0",
        "baudrate": 115200,
        "timeout": 0.5
    }

def _get_esp32_connection() -> Optional[ESP32Connection]:
    """Get or initialize the ESP32 connection (lazy loading)."""
    global _ESP32_CONN
    if _ESP32_CONN is None:
        try:
            config = _load_motor_config()
            cfg = ESP32SerialConfig(
                port=config.get("port", "/dev/ttyUSB0"),
                baudrate=config.get("baudrate", 115200),
                timeout=float(config.get("timeout", 0.5))
            )
            _ESP32_CONN = ESP32Connection(cfg)
            print("[MOTORS] ESP32 connection established")
        except Exception as e:
            print(f"[MOTORS] Error connecting to ESP32: {e}")
            _ESP32_CONN = False  # Mark as failed to avoid retry
    return _ESP32_CONN if _ESP32_CONN else None

def espEnable(on: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Enable/disable the stepper driver."""
    try:
        conn = _get_esp32_connection()
        if not conn:
            return {"error": "ESP32 connection not available"}
        return conn.send({"cmd": "enable", "motor": motor_id, "value": bool(on)})
    except Exception as e:
        return {"error": str(e)}

def espSetDirection(forward: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set motor direction: True=forward, False=reverse."""
    try:
        conn = _get_esp32_connection()
        if not conn:
            return {"error": "ESP32 connection not available"}
        # Note: The new interface doesn't have a separate set_direction command
        # Direction is controlled via the forward parameter in turn_degrees
        return {"status": "ok", "message": "Direction is controlled via forward parameter in movement commands"}
    except Exception as e:
        return {"error": str(e)}

def espSetSpeed(sps: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set speed in steps/sec."""
    try:
        conn = _get_esp32_connection()
        if not conn:
            return {"error": "ESP32 connection not available"}
        return conn.send({"cmd": "set_speed", "motor": motor_id, "sps": float(sps)})
    except Exception as e:
        return {"error": str(e)}

def espStart(sps: Any, forward: Optional[Any] = None, motor_id: str = "motor1") -> Dict[str, Any]:
    """Start continuous rotation at speed with optional direction.
    
    Note: The new interface doesn't support true continuous motion without a target.
    This will start indefinite motion by moving a very large number of degrees.
    """
    try:
        conn = _get_esp32_connection()
        if not conn:
            return {"error": "ESP32 connection not available"}
        
        # Set speed first
        conn.send({"cmd": "set_speed", "motor": motor_id, "sps": float(sps)})
        
        # Move a very large distance to simulate continuous motion
        # Using 10000 degrees with no explicit timeout to keep motors running
        fwd = forward if forward is not None else True
        return conn.send({
            "cmd": "turn_degrees",
            "motor": motor_id,
            "degrees": 10000.0,
            "forward": bool(fwd)
        })
    except Exception as e:
        return {"error": str(e)}

def espMoveSteps(steps: Any, sps: Optional[Any] = None, forward: Optional[Any] = None, motor_id: str = "motor1") -> Dict[str, Any]:
    """Move a finite number of steps with optional speed and direction override.
    
    Note: The new interface uses degrees instead of steps, so this converts steps to degrees
    assuming STEPS_PER_DEGREE = 8.889 (typical for common stepper configs)
    """
    try:
        conn = _get_esp32_connection()
        if not conn:
            return {"error": "ESP32 connection not available"}
        
        # Convert steps to degrees (8.889 steps/degree is a common default)
        STEPS_PER_DEGREE = 8.889
        degrees = float(steps) / STEPS_PER_DEGREE
        
        if sps is not None:
            conn.send({"cmd": "set_speed", "motor": motor_id, "sps": float(sps)})
        
        fwd = forward if forward is not None else True
        return conn.send({
            "cmd": "turn_degrees",
            "motor": motor_id,
            "degrees": degrees,
            "forward": bool(fwd)
        })
    except Exception as e:
        return {"error": str(e)}

def espStop(motor_id: str = "motor1") -> Dict[str, Any]:
    """Stop motion."""
    try:
        conn = _get_esp32_connection()
        if not conn:
            return {"error": "ESP32 connection not available"}
        return conn.send({"cmd": "stop", "motor": motor_id})
    except Exception as e:
        return {"error": str(e)}

def espSetMicrosteps(value: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set TMC2209 microstepping value (e.g., 16, 32).
    
    NOT SUPPORTED in new interface - microstepping must be configured on the ESP32 firmware.
    """
    return {"error": "Microstepping configuration is not supported in this interface. Configure on ESP32 firmware instead."}

def espSetCurrent(mA: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set RMS motor current in milliamps.
    
    NOT SUPPORTED in new interface - motor current must be configured on the ESP32 firmware.
    """
    return {"error": "Motor current configuration is not supported in this interface. Configure on ESP32 firmware instead."}

def espSetMode(mode: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set chopper mode: 'stealth' or 'spread'.
    
    NOT SUPPORTED in new interface - chopper mode must be configured on the ESP32 firmware.
    """
    return {"error": "Chopper mode configuration is not supported in this interface. Configure on ESP32 firmware instead."}

def espSetAccel(sps2: Any, motor_id: str = "motor1") -> Dict[str, Any]:
    """Set acceleration in steps/sec^2 for ramping.
    
    NOT SUPPORTED in new interface - acceleration must be configured on the ESP32 firmware.
    """
    return {"error": "Acceleration configuration is not supported in this interface. Configure on ESP32 firmware instead."}

def espStatus(motor_id: str = "motor1") -> Dict[str, Any]:
    """Query motor status."""
    try:
        conn = _get_esp32_connection()
        if not conn:
            return {"error": "ESP32 connection not available"}
        return conn.send({"cmd": "status", "motor": motor_id})
    except Exception as e:
        return {"error": str(e)}

def espStatusAll() -> Dict[str, Any]:
    """Query status of all motors."""
    try:
        conn = _get_esp32_connection()
        if not conn:
            return {"error": "ESP32 connection not available"}
        return conn.list_motors()
    except Exception as e:
        return {"error": str(e)}

def espTurnDegrees(degrees: Any, forward: Any = True, motor_id: str = "motor1") -> Dict[str, Any]:
    """Move motor a specified number of degrees."""
    try:
        conn = _get_esp32_connection()
        if not conn:
            return {"error": "ESP32 connection not available"}
        return conn.send({
            "cmd": "turn_degrees",
            "motor": motor_id,
            "degrees": float(degrees),
            "forward": bool(forward)
        })
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
        elif cmd_type == 'turn_degrees':
            degrees = command_data.get('degrees', 0)
            forward = command_data.get('forward', True)
            return espTurnDegrees(degrees, forward, motor_id)
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
    # Debug
    "echo": echo,
    # Main track requests
    "trackCoordinates": trackCoordinates,
    "stopTracking": stop_tracking,
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
    "espTurnDegrees": espTurnDegrees,
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
