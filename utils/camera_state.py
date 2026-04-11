"""Camera availability state management"""
import asyncio
import time
import subprocess
from threading import Lock
from utils.liveview_state import is_liveview_enabled

class CameraState:
    """Thread-safe camera availability state"""
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._available = False
        self._last_check_time = 0
        self._command_lock = Lock()
        self._initialized = True
    
    def is_available(self) -> bool:
        """Check if camera is currently available"""
        with self._lock:
            return self._available
    
    def set_available(self, available: bool):
        """Set camera availability status"""
        with self._lock:
            changed = self._available != available
            self._available = available
            self._last_check_time = time.time()
            if changed:
                status = "available" if available else "unavailable"
                print(f"[camera_state] Camera is now {status}")
    
    def get_last_check_time(self) -> float:
        """Get timestamp of last availability check"""
        with self._lock:
            return self._last_check_time
    
    def pause_liveview_for_command(self):
        """Temporarily pause live view to execute a camera command.
        
        This kills any running gphoto2 processes and waits for them to fully terminate.
        Live view will automatically restart after the command completes.
        """
        try:
            # Kill any running gphoto2 processes
            print("[camera_state] Pausing live view for camera command...")
            subprocess.run(["pkill", "-9", "gphoto2"], capture_output=True, timeout=2)
            # Wait for processes to fully terminate and camera to be released
            time.sleep(0.5)
        except Exception as e:
            print(f"[camera_state] Error pausing live view: {e}")
    
    def get_command_lock(self):
        """Get the lock for executing camera commands"""
        return self._command_lock


# Global singleton instance
camera_state = CameraState()


async def camera_scanner_task(check_interval: float = 2.0):
    """Background task that continuously scans for camera availability
    
    Args:
        check_interval: Time in seconds between camera checks
    """
    from core.camera.controller import Camera
    
    print(f"[camera_scanner] Started camera scanner (checking every {check_interval}s)")
    
    while True:
        try:
            # Do not probe camera while liveview is actively streaming.
            # Running gphoto2 auto-detect concurrently can contend for USB access.
            if is_liveview_enabled():
                await asyncio.sleep(check_interval)
                continue

            # Quick check without retries for the background scanner
            from subprocess import run
            result = run(["gphoto2", "--auto-detect"], 
                        capture_output=True, text=True, timeout=3)
            output = result.stdout.strip()
            
            if "usb:" in output.lower():
                if not camera_state.is_available():
                    # Camera just became available
                    camera_state.set_available(True)
                    # Try to release viewfinder to prepare camera
                    try:
                        Camera.releaseViewfinder()
                    except:
                        pass
            else:
                if camera_state.is_available():
                    camera_state.set_available(False)
        
        except Exception as e:
            # Scanner should never crash
            if camera_state.is_available():
                camera_state.set_available(False)
        
        # Wait before next check
        await asyncio.sleep(check_interval)
