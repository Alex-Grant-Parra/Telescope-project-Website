import threading
import time
from utils.location import get_current_location
from utils.Tools import hour_angle
from utils.telescope_state import set_telescope_coords, get_telescope_coords, get_slew_config

# Motor control
from esp32.interfaceESP32 import ESP32Connection, ESP32SerialConfig, ESP32Motor


POLARIS_RA_DEG = 37.95456067
POLARIS_DEC_DEG = 89.26410897

# Global ESP32 connection instance (lazy loaded)
_esp32_conn = None

# Global tracking state
_tracking_thread = None
_tracking_active = False
_target_object = None  # {"name": str, "ra": float, "dec": float, "mag": float}

# Motor initialization flag
_motors_initialized = False


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


def _initialize_motors():
    """Initialize motors on the ESP32 if not already done."""
    global _motors_initialized
    
    if _motors_initialized:
        return True
    
    conn = _get_esp32_connection()
    if not conn:
        print("[tracking] Cannot initialize motors: ESP32 connection not available")
        return False
    
    try:
        print("[tracking] Initializing motors on ESP32...")
        
        # Check if motors already exist
        try:
            motors = conn.list_motors()
            print(f"[tracking] Existing motors: {motors}")
        except Exception as e:
            print(f"[tracking] Could not list motors: {e}")
            motors = {}
        
        # Create motor1 (RA) if it doesn't exist
        if "motor1" not in str(motors):
            print("[tracking] Creating motor1 (RA motor)...")
            try:
                result = ESP32Motor.create(
                    conn=conn,
                    motor_id="motor1",
                    step_pin=27,
                    dir_pin=14,
                    en_pin=26,
                    steps_per_rev=1600,
                    engage=True,
                    replace=True
                )
                print(f"[tracking] Motor1 (RA) created successfully: {result}")
            except Exception as e:
                print(f"[tracking] Error creating motor1: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print("[tracking] Motor1 (RA) already exists")
        
        # Create motor2 (DEC) if it doesn't exist
        if "motor2" not in str(motors):
            print("[tracking] Creating motor2 (DEC motor)...")
            try:
                result = ESP32Motor.create(
                    conn=conn,
                    motor_id="motor2",
                    step_pin=33,
                    dir_pin=32,
                    en_pin=25,
                    steps_per_rev=1600,
                    engage=True,
                    replace=True
                )
                print(f"[tracking] Motor2 (DEC) created successfully: {result}")
            except Exception as e:
                print(f"[tracking] Warning: Could not create motor2 (DEC): {e}")
                import traceback
                traceback.print_exc()
                # Continue even if motor2 fails - might only have 1 motor
        else:
            print("[tracking] Motor2 (DEC) already exists")
        
        _motors_initialized = True
        print("[tracking] Motor initialization complete")
        return True
        
    except Exception as e:
        print(f"[tracking] Error initializing motors: {e}")
        return False


def _move_motors(delta_ha: float, delta_dec: float) -> None:
    """Move motors to compensate for HA and Dec deltas using multi-phase slewing.
    
    Applies gear ratios to scale motor movements correctly.
    Once centered, motors continue at tracking speed indefinitely.
    
    Args:
        delta_ha: Hour angle difference in degrees (positive = east/forward)
        delta_dec: Declination difference in degrees (positive = north)
    """
    conn = _get_esp32_connection()
    if not conn:
        print("[tracking] Warning: ESP32 connection not available; cannot move motors")
        return
    
    # Verify motors exist on ESP32 and re-initialize if needed
    try:
        motors = conn.list_motors()
        if "motor1" not in str(motors) or "motor2" not in str(motors):
            print(f"[tracking] Motors not found on ESP32 (existing: {motors}), reinitializing...")
            global _motors_initialized
            _motors_initialized = False  # Force re-initialization
    except Exception as e:
        print(f"[tracking] Could not verify motors: {e}, attempting initialization...")
        _motors_initialized = False
    
    # Ensure motors are initialized before trying to move them
    if not _initialize_motors():
        print("[tracking] Warning: Motors not initialized; cannot move")
        return
    
    config = get_slew_config()
    
    # Apply gear ratios to convert sky movement to motor movement
    # For a 360:1 gearbox, a 1° sky movement requires 360° motor rotation
    ra_gear_ratio = config.get("ra_gear_ratio", 360.0)
    dec_gear_ratio = config.get("dec_gear_ratio", 144.0)
    
    motor_delta_ha = delta_ha * ra_gear_ratio
    motor_delta_dec = delta_dec * dec_gear_ratio
    
    # Absolute distances to target (in motor degrees)
    abs_motor_delta_ha = abs(motor_delta_ha)
    abs_motor_delta_dec = abs(motor_delta_dec)
    
    # Thresholds are in sky degrees, so we need to scale them too
    slew_threshold_motor = config["slew_threshold_degrees"] * ra_gear_ratio
    center_threshold_motor = config["center_threshold_degrees"] * ra_gear_ratio
    
    print(f"[tracking] Sky deltas: HA={delta_ha:.4f}°, Dec={delta_dec:.4f}°")
    print(f"[tracking] Motor deltas (with gear ratios {ra_gear_ratio}:1, {dec_gear_ratio}:1): HA={motor_delta_ha:.4f}°, Dec={motor_delta_dec:.4f}°")
    
    try:
        # Each motor moves independently at the appropriate speed for its distance
        
        # RA Motor: Choose speed based on distance
        if abs_motor_delta_ha > slew_threshold_motor:
            # Phase 1: Slew at high speed
            try:
                print(f"[tracking] RA motor slewing: {motor_delta_ha:.4f}° (motor) for {delta_ha:.4f}° (sky) at {config['slew_speed_sps']:.1f} sps")
                speed_resp = conn.send({"cmd": "set_speed", "motor": "motor1", "sps": config["slew_speed_sps"]})
                print(f"[tracking] RA set_speed response: {speed_resp}")
                move_resp = conn.send({
                    "cmd": "turn_degrees",
                    "motor": "motor1",
                    "degrees": abs_motor_delta_ha,
                    "forward": delta_ha > 0
                })
                print(f"[tracking] RA turn_degrees response: {move_resp}")
            except Exception as e:
                print(f"[tracking] Error moving RA motor: {e}")
                import traceback
                traceback.print_exc()
        elif abs_motor_delta_ha > center_threshold_motor:
            # Phase 2: Refine at medium speed
            try:
                conn.send({"cmd": "set_speed", "motor": "motor1", "sps": config["refine_speed_sps"]})
                conn.send({
                    "cmd": "turn_degrees",
                    "motor": "motor1",
                    "degrees": abs_motor_delta_ha,
                    "forward": delta_ha > 0
                })
                print(f"[tracking] RA motor refining: {motor_delta_ha:.4f}° (motor) for {delta_ha:.4f}° (sky) at {config['refine_speed_sps']:.1f} sps")
            except Exception as e:
                print(f"[tracking] Error refining RA motor: {e}")
        else:
            # Phase 3: Already centered, set to tracking speed
            try:
                conn.send({"cmd": "set_speed", "motor": "motor1", "sps": config["tracking_speed_sps"]})
                print(f"[tracking] RA motor centered, tracking at {config['tracking_speed_sps']:.1f} sps")
            except Exception as e:
                print(f"[tracking] Error setting RA tracking speed: {e}")
        
        # DEC Motor: Choose speed based on distance (independent of RA)
        if abs_motor_delta_dec > slew_threshold_motor:
            # Phase 1: Slew at high speed
            try:
                print(f"[tracking] DEC motor slewing: {motor_delta_dec:.4f}° (motor) for {delta_dec:.4f}° (sky) at {config['slew_speed_sps']:.1f} sps")
                speed_resp = conn.send({"cmd": "set_speed", "motor": "motor2", "sps": config["slew_speed_sps"]})
                print(f"[tracking] DEC set_speed response: {speed_resp}")
                move_resp = conn.send({
                    "cmd": "turn_degrees",
                    "motor": "motor2",
                    "degrees": abs_motor_delta_dec,
                    "forward": delta_dec > 0
                })
                print(f"[tracking] DEC turn_degrees response: {move_resp}")
            except Exception as e:
                print(f"[tracking] Error moving DEC motor: {e}")
                import traceback
                traceback.print_exc()
        elif abs_motor_delta_dec > center_threshold_motor:
            # Phase 2: Refine at medium speed
            try:
                conn.send({"cmd": "set_speed", "motor": "motor2", "sps": config["refine_speed_sps"]})
                conn.send({
                    "cmd": "turn_degrees",
                    "motor": "motor2",
                    "degrees": abs_motor_delta_dec,
                    "forward": delta_dec > 0
                })
                print(f"[tracking] DEC motor refining: {motor_delta_dec:.4f}° (motor) for {delta_dec:.4f}° (sky) at {config['refine_speed_sps']:.1f} sps")
            except Exception as e:
                print(f"[tracking] Error refining DEC motor: {e}")
        else:
            # Phase 3: Already centered, set to tracking speed
            try:
                conn.send({"cmd": "set_speed", "motor": "motor2", "sps": config["tracking_speed_sps"]})
                print(f"[tracking] DEC motor centered, tracking at {config['tracking_speed_sps']:.1f} sps")
            except Exception as e:
                print(f"[tracking] Error setting DEC tracking speed: {e}")
    
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
            
            # Recalculate position frequently for live updates
            location = get_current_location()
            if location is None:
                time.sleep(1)
                continue
            
            longitude = location.get('longitude')
            latitude = location.get('latitude')
            
            # Get target coordinates (RA is time-invariant)
            target_ra = _target_object['ra']
            target_dec = _target_object['dec']
            target_ha = hour_angle(target_ra, longitude)
            
            # Get current telescope position (stored as RA)
            coords = get_telescope_coords() or {}
            current_ra = coords.get('right_ascension', 0.0)
            current_dec = coords.get('declination', 0.0)
            
            # Recalculate current HA from stored RA (accounts for Earth rotation)
            current_ha = hour_angle(current_ra, longitude) if current_ra != 0.0 else 0.0
            
            # Calculate drift
            delta_ha = target_ha - current_ha
            delta_dec = target_dec - current_dec
            
            config = get_slew_config()
            ra_gear_ratio = config.get("ra_gear_ratio", 360.0)
            dec_gear_ratio = config.get("dec_gear_ratio", 144.0)
            
            abs_delta_ha = abs(delta_ha)
            abs_delta_dec = abs(delta_dec)
            
            # If significant drift detected, make micro-adjustments
            if abs_delta_ha > config["center_threshold_degrees"] or abs_delta_dec > config["center_threshold_degrees"]:
                print(f"[tracking] Position drift detected: HA={delta_ha:.4f}° (sky), Dec={delta_dec:.4f}° (sky). Making correction.")
                
                conn = _get_esp32_connection()
                if conn:
                    # Apply gear ratios for motor movements
                    motor_delta_ha = delta_ha * ra_gear_ratio
                    motor_delta_dec = delta_dec * dec_gear_ratio
                    
                    # Make small corrective movements
                    if abs_delta_ha > config["center_threshold_degrees"]:
                        try:
                            # Use a slightly faster speed for quick corrections
                            correction_speed = config["tracking_speed_sps"] * 2
                            conn.send({"cmd": "set_speed", "motor": "motor1", "sps": correction_speed})
                            conn.send({
                                "cmd": "turn_degrees",
                                "motor": "motor1",
                                "degrees": abs(motor_delta_ha),
                                "forward": delta_ha > 0
                            })
                            print(f"[tracking] RA correction: {motor_delta_ha:.4f}° (motor) for {delta_ha:.4f}° (sky)")
                        except Exception as e:
                            print(f"[tracking] Error correcting RA: {e}")
                    
                    if abs_delta_dec > config["center_threshold_degrees"]:
                        try:
                            correction_speed = config["tracking_speed_sps"] * 2
                            conn.send({"cmd": "set_speed", "motor": "motor2", "sps": correction_speed})
                            conn.send({
                                "cmd": "turn_degrees",
                                "motor": "motor2",
                                "degrees": abs(motor_delta_dec),
                                "forward": delta_dec > 0
                            })
                            print(f"[tracking] DEC correction: {motor_delta_dec:.4f}° (motor) for {delta_dec:.4f}° (sky)")
                        except Exception as e:
                            print(f"[tracking] Error correcting Dec: {e}")
                    
                    # Return to tracking speed
                    try:
                        conn.send({"cmd": "set_speed", "motor": "motor1", "sps": config["tracking_speed_sps"]})
                        conn.send({"cmd": "set_speed", "motor": "motor2", "sps": config["tracking_speed_sps"]})
                    except Exception as e:
                        print(f"[tracking] Error resetting to tracking speed: {e}")
            
            # Update telescope state with current target's RA (not HA)
            # Include target HA for live tracking display (HA changes as Earth rotates)
            set_telescope_coords(target_ra, target_dec, source="tracking", hour_angle=target_ha)
            
            time.sleep(1.0)  # Update every second for live feedback
        
        except Exception as e:
            print(f"[tracking] Error in tracking loop: {e}")
            time.sleep(2)
    
    print("[tracking] Continuous tracking thread stopped")


def stop_tracking() -> None:
    """Stop continuous tracking and motors."""
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
    
    # Stop all motors
    conn = _get_esp32_connection()
    if conn:
        print("[tracking] Stopping motors...")
        try:
            # Stop motor1 (RA)
            try:
                conn.send({"cmd": "stop", "motor": "motor1"})
                print("[tracking] Motor1 (RA) stopped")
            except Exception as e:
                print(f"[tracking] Error stopping motor1: {e}")
            
            # Stop motor2 (DEC)
            try:
                conn.send({"cmd": "stop", "motor": "motor2"})
                print("[tracking] Motor2 (DEC) stopped")
            except Exception as e:
                print(f"[tracking] Error stopping motor2: {e}")
        except Exception as e:
            print(f"[tracking] Error stopping motors: {e}")
    else:
        print("[tracking] Warning: ESP32 connection not available to stop motors")


def _set_polaris_alignment(location: dict) -> None:
    """Set telescope to Polaris coordinates for polar alignment."""
    longitude = location.get('longitude')
    if longitude is None:
        print("[tracking] Warning: Longitude missing; cannot set Polaris alignment.")
        return
    # Store Polaris RA (not HA) in state
    set_telescope_coords(POLARIS_RA_DEG, POLARIS_DEC_DEG, source="polaris")


def trackCoordinates(name, ra, dec, mag):
    """Start tracking a celestial object with continuous sky rotation compensation.
    
    The telescope will:
    1. Slew to the target at high speed
    2. Refine approach at medium speed
    3. Center on target at slow speed
    4. Continuously track the object as the sky rotates
    
    Args:
        name: Object name
        ra: Right ascension in degrees (can be string or float)
        dec: Declination in degrees (can be string or float)
        mag: Magnitude
    """
    global _tracking_active, _tracking_thread, _target_object
    
    # Convert string inputs to floats if needed
    try:
        ra = float(ra)
        dec = float(dec)
    except (ValueError, TypeError) as e:
        print(f"[tracking] Error: Invalid RA or Dec format: {e}")
        return
    
    print(f"[tracking] Acquiring target: {name}, RA: {ra}, Dec: {dec}, Mag: {mag}")
    
    # Get current location from config
    location = get_current_location()
    if location is None:
        print("[tracking] Warning: Location data not available. Cannot calculate hour angle.")
        return
    
    # Extract longitude and latitude from location JSON
    longitude = location.get('longitude')
    latitude = location.get('latitude')
    print(f"[tracking] Observer location: Longitude={longitude}, Latitude={latitude}")

    # Convert target RA to hour angle using current location and time
    TargetHA = hour_angle(ra, longitude)
    TargetDec = dec
    print(f"[tracking] Target: {name} - RA={ra:.4f}°, Dec={dec:.4f}°")
    print(f"[tracking] Target Hour Angle (current): HA={TargetHA:.4f}°")

    # Read current telescope coordinates from state (stored as RA, not HA)
    coords = get_telescope_coords() or {}
    CurrentRA = coords.get('right_ascension', 0.0)
    CurrentDec = coords.get('declination', 0.0)
    
    # Convert current telescope RA to current hour angle
    # This accounts for Earth's rotation since last slew
    CurrentHA = hour_angle(CurrentRA, longitude) if CurrentRA != 0.0 else 0.0
    
    print(f"[tracking] Current telescope: RA={CurrentRA:.4f}°, Dec={CurrentDec:.4f}°")
    print(f"[tracking] Current Hour Angle (recalculated): HA={CurrentHA:.4f}°")

    # Calculate the difference between target and current coordinates
    DeltaHA = TargetHA - CurrentHA
    DeltaDec = TargetDec - CurrentDec
    print(f"[tracking] Delta to move: HA={DeltaHA:.4f}°, Dec={DeltaDec:.4f}°")
    print(f"[tracking] Absolute delta: HA={abs(DeltaHA):.4f}°, Dec={abs(DeltaDec):.4f}°")

    # Slew, refine, and center on target
    if abs(DeltaHA) > 0.001 or abs(DeltaDec) > 0.001:
        print(f"[tracking] Movement required, calling _move_motors...")
        _move_motors(DeltaHA, DeltaDec)
        # Store the target's RA (not HA) so it remains valid as time passes
        set_telescope_coords(ra, dec, source="tracking")
        print(f"[tracking] Telescope state updated: RA={ra:.4f}°, Dec={dec:.4f}°")
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
    
    # Note: ifAligned() check removed here - it was overwriting target coordinates with Polaris
    # Polaris alignment should be done separately via a dedicated alignment command


def ifAligned():
    # placeholder, will link to a momentary button in the future
    # will return true if the telescope is polar aligned, otherwise false
    return True


