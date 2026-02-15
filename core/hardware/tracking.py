import threading
import time
from utils.location import get_current_location
from utils.Tools import hour_angle
from utils.telescope_state import set_telescope_coords, get_telescope_coords, get_slew_config

# Motor control
from esp32.interfaceESP32 import ESP32Connection, ESP32SerialConfig


POLARIS_RA_DEG = 37.95456067
POLARIS_DEC_DEG = 89.26410897

# Global ESP32 connection instance (lazy loaded)
_esp32_conn = None

# Global tracking state
_tracking_thread = None
_tracking_active = False
_target_object = None  # {"name": str, "ra": float, "dec": float, "mag": float}


def _get_esp32_connection():
    """Get or initialize the ESP32 connection (lazy loading)."""
    global _esp32_conn
    if _esp32_conn is None:
        try:
            cfg = ESP32SerialConfig(port="/dev/ttyUSB0", baudrate=115200)
            _esp32_conn = ESP32Connection(cfg)
            print("[tracking] ESP32 connection established")
        except Exception as e:
            print(f"[tracking] Error connecting to ESP32: {e}")
            _esp32_conn = False  # Mark as failed to avoid retry
    return _esp32_conn if _esp32_conn else None


def _move_motors(delta_ha: float, delta_dec: float) -> None:
    """Move motors to compensate for HA and Dec deltas using multi-phase slewing.
    
    Once centered, motors continue at tracking speed indefinitely.
    
    Args:
        delta_ha: Hour angle difference in degrees (positive = east/forward)
        delta_dec: Declination difference in degrees (positive = north)
    """
    conn = _get_esp32_connection()
    if not conn:
        print("[tracking] Warning: ESP32 connection not available; cannot move motors")
        return
    
    config = get_slew_config()
    
    # Absolute distances to target
    abs_delta_ha = abs(delta_ha)
    abs_delta_dec = abs(delta_dec)
    
    print(f"[tracking] Slewing: HA delta={delta_ha:.4f}°, Dec delta={delta_dec:.4f}°")
    
    try:
        # Phase 1: Slew at high speed until within slew threshold
        if abs_delta_ha > config["slew_threshold_degrees"] or abs_delta_dec > config["slew_threshold_degrees"]:
            print(f"[tracking] Phase 1: Slewing at {config['slew_speed_sps']:.1f} sps")
            
            if abs_delta_ha > config["slew_threshold_degrees"]:
                try:
                    conn.send({"cmd": "set_speed", "motor": "motor1", "sps": config["slew_speed_sps"]})
                    conn.send({
                        "cmd": "turn_degrees",
                        "motor": "motor1",
                        "degrees": abs_delta_ha,
                        "forward": delta_ha > 0
                    })
                    print(f"[tracking] RA motor commanded: {delta_ha:.4f}° at slew speed")
                except Exception as e:
                    print(f"[tracking] Error moving RA motor: {e}")
            
            if abs_delta_dec > config["slew_threshold_degrees"]:
                try:
                    conn.send({"cmd": "set_speed", "motor": "motor2", "sps": config["slew_speed_sps"]})
                    conn.send({
                        "cmd": "turn_degrees",
                        "motor": "motor2",
                        "degrees": abs_delta_dec,
                        "forward": delta_dec > 0
                    })
                    print(f"[tracking] DEC motor commanded: {delta_dec:.4f}° at slew speed")
                except Exception as e:
                    print(f"[tracking] Error moving DEC motor: {e}")
        
        # Phase 2: Refine at medium speed until within center threshold
        elif abs_delta_ha > config["center_threshold_degrees"] or abs_delta_dec > config["center_threshold_degrees"]:
            print(f"[tracking] Phase 2: Refining at {config['refine_speed_sps']:.1f} sps")
            
            if abs_delta_ha > config["center_threshold_degrees"]:
                try:
                    conn.send({"cmd": "set_speed", "motor": "motor1", "sps": config["refine_speed_sps"]})
                    conn.send({
                        "cmd": "turn_degrees",
                        "motor": "motor1",
                        "degrees": abs_delta_ha,
                        "forward": delta_ha > 0
                    })
                    print(f"[tracking] RA motor refining: {delta_ha:.4f}° at refine speed")
                except Exception as e:
                    print(f"[tracking] Error refining RA motor: {e}")
            
            if abs_delta_dec > config["center_threshold_degrees"]:
                try:
                    conn.send({"cmd": "set_speed", "motor": "motor2", "sps": config["refine_speed_sps"]})
                    conn.send({
                        "cmd": "turn_degrees",
                        "motor": "motor2",
                        "degrees": abs_delta_dec,
                        "forward": delta_dec > 0
                    })
                    print(f"[tracking] DEC motor refining: {delta_dec:.4f}° at refine speed")
                except Exception as e:
                    print(f"[tracking] Error refining DEC motor: {e}")
        
        # Phase 3: Set motors to tracking speed for continuous sky tracking
        else:
            print(f"[tracking] Centered on target. Motors set to continuous tracking at {config['tracking_speed_sps']:.1f} sps")
            
            try:
                # Set both motors to tracking speed - they will move continuously to keep up with the sky
                conn.send({"cmd": "set_speed", "motor": "motor1", "sps": config["tracking_speed_sps"]})
                conn.send({"cmd": "set_speed", "motor": "motor2", "sps": config["tracking_speed_sps"]})
                print(f"[tracking] RA and DEC motors now tracking at {config['tracking_speed_sps']:.1f} sps")
            except Exception as e:
                print(f"[tracking] Error setting tracking speed: {e}")
    
    except Exception as e:
        print(f"[tracking] Error in motor movement: {e}")


def _continuous_tracking_loop() -> None:
    """Background thread that continuously monitors and adjusts tracking."""
    global _tracking_active, _target_object
    
    print("[tracking] Continuous tracking thread started")
    
    while _tracking_active:
        try:
            if _target_object is None:
                time.sleep(1)
                continue
            
            # Recalculate position every 2 seconds
            location = get_current_location()
            if location is None:
                time.sleep(2)
                continue
            
            longitude = location.get('longitude')
            latitude = location.get('latitude')
            
            # Get target coordinates
            target_ha = hour_angle(_target_object['ra'], longitude)
            target_dec = _target_object['dec']
            
            # Get current telescope position
            coords = get_telescope_coords() or {}
            current_ha = coords.get('hour_angle', 0.0)
            current_dec = coords.get('declination', 0.0)
            
            # Calculate drift
            delta_ha = target_ha - current_ha
            delta_dec = target_dec - current_dec
            
            config = get_slew_config()
            abs_delta_ha = abs(delta_ha)
            abs_delta_dec = abs(delta_dec)
            
            # If significant drift detected, make micro-adjustments
            if abs_delta_ha > config["center_threshold_degrees"] or abs_delta_dec > config["center_threshold_degrees"]:
                print(f"[tracking] Position drift detected: HA={delta_ha:.4f}°, Dec={delta_dec:.4f}°. Making correction.")
                
                conn = _get_esp32_connection()
                if conn:
                    # Make small corrective movements
                    if abs_delta_ha > config["center_threshold_degrees"]:
                        try:
                            # Use a slightly faster speed for quick corrections
                            correction_speed = config["tracking_speed_sps"] * 2
                            conn.send({"cmd": "set_speed", "motor": "motor1", "sps": correction_speed})
                            conn.send({
                                "cmd": "turn_degrees",
                                "motor": "motor1",
                                "degrees": abs_delta_ha,
                                "forward": delta_ha > 0
                            })
                        except Exception as e:
                            print(f"[tracking] Error correcting RA: {e}")
                    
                    if abs_delta_dec > config["center_threshold_degrees"]:
                        try:
                            correction_speed = config["tracking_speed_sps"] * 2
                            conn.send({"cmd": "set_speed", "motor": "motor2", "sps": correction_speed})
                            conn.send({
                                "cmd": "turn_degrees",
                                "motor": "motor2",
                                "degrees": abs_delta_dec,
                                "forward": delta_dec > 0
                            })
                        except Exception as e:
                            print(f"[tracking] Error correcting Dec: {e}")
                    
                    # Return to tracking speed
                    try:
                        conn.send({"cmd": "set_speed", "motor": "motor1", "sps": config["tracking_speed_sps"]})
                        conn.send({"cmd": "set_speed", "motor": "motor2", "sps": config["tracking_speed_sps"]})
                    except Exception as e:
                        print(f"[tracking] Error resetting to tracking speed: {e}")
            
            # Update telescope state with current coordinates
            set_telescope_coords(target_ha, target_dec, source="tracking")
            
            time.sleep(2)  # Wait 2 seconds before next check
        
        except Exception as e:
            print(f"[tracking] Error in tracking loop: {e}")
            time.sleep(2)
    
    print("[tracking] Continuous tracking thread stopped")


def stop_tracking() -> None:
    """Stop continuous tracking."""
    global _tracking_active, _tracking_thread, _target_object
    
    if _tracking_active:
        print("[tracking] Stopping continuous tracking")
        _tracking_active = False
        
        # Wait for thread to finish
        if _tracking_thread and _tracking_thread.is_alive():
            _tracking_thread.join(timeout=5)
        
        _target_object = None
        _tracking_thread = None
        
        print("[tracking] Tracking stopped")


def _set_polaris_alignment(location: dict) -> None:
    """Set telescope to Polaris coordinates for polar alignment."""
    longitude = location.get('longitude')
    if longitude is None:
        print("[tracking] Warning: Longitude missing; cannot set Polaris alignment.")
        return
    polaris_ha = hour_angle(POLARIS_RA_DEG, longitude)
    set_telescope_coords(polaris_ha, POLARIS_DEC_DEG, source="polaris")


def trackCoordinates(name, ra, dec, mag):
    """Start tracking a celestial object with continuous sky rotation compensation.
    
    The telescope will:
    1. Slew to the target at high speed
    2. Refine approach at medium speed
    3. Center on target at slow speed
    4. Continuously track the object as the sky rotates
    
    Args:
        name: Object name
        ra: Right ascension in degrees
        dec: Declination in degrees
        mag: Magnitude
    """
    global _tracking_active, _tracking_thread, _target_object
    
    print(f"[tracking] Acquiring target: {name}, RA: {ra}, Dec: {dec}, Mag: {mag}")
    
    # Get current location from config
    location = get_current_location()
    if location is None:
        print("[tracking] Warning: Location data not available. Cannot calculate hour angle.")
        return
    
    # Extract longitude and latitude from location JSON
    longitude = location.get('longitude')
    latitude = location.get('latitude')

    # Convert RA to hour angle using current location
    TargetHA = hour_angle(ra, longitude)
    TargetDec = dec

    # Read current telescope coordinates from state
    coords = get_telescope_coords() or {}
    CurrentHA = coords.get('hour_angle', 0.0)
    CurrentDec = coords.get('declination', 0.0)

    # Calculate the difference between target and current coordinates
    DeltaHA = TargetHA - CurrentHA
    DeltaDec = TargetDec - CurrentDec

    # Slew, refine, and center on target
    if abs(DeltaHA) > 0.001 or abs(DeltaDec) > 0.001:
        _move_motors(DeltaHA, DeltaDec)
        set_telescope_coords(TargetHA, TargetDec, source="tracking")
        print(f"[tracking] Telescope slewing to HA={TargetHA:.4f}°, Dec={TargetDec:.4f}°")
    else:
        print(f"[tracking] Telescope already at target")

    # Store target for continuous tracking
    _target_object = {"name": name, "ra": ra, "dec": dec, "mag": mag}
    
    # Start continuous tracking thread if not already running
    if not _tracking_active:
        _tracking_active = True
        _tracking_thread = threading.Thread(target=_continuous_tracking_loop, daemon=True)
        _tracking_thread.start()
        print(f"[tracking] Continuous tracking started for {name}")

    if ifAligned():
        _set_polaris_alignment(location)


def ifAligned():
    # placeholder, will link to a momentary button in the future
    # will return true if the telescope is polar aligned, otherwise false
    return True


