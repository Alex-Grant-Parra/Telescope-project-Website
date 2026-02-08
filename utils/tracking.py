from utils.location import get_current_location
from utils.Tools import hour_angle
from utils.telescope_state import set_telescope_coords, get_telescope_coords

# Motor control
try:
    from core.hardware.esp32_motor import ESP32MotorArray
except ImportError:
    ESP32MotorArray = None

POLARIS_RA_DEG = 37.95456067
POLARIS_DEC_DEG = 89.26410897

# Motor configuration: steps per degree (adjust based on your gear ratios)
# Typical: 200 steps/revolution, 16 microsteps = 3200 microsteps/rev = 8.889 steps/degree
STEPS_PER_DEGREE_HA = 8.889   # RA/Hour Angle motor (motor1)
STEPS_PER_DEGREE_DEC = 8.889  # Declination motor (motor2)

# Global motor array instance (lazy loaded)
_motor_array = None


def _get_motor_array():
    """Get or initialize the motor array (lazy loading)."""
    global _motor_array
    if _motor_array is None and ESP32MotorArray is not None:
        try:
            motor_configs = [
                {"motor_id": "motor1", "port": "/dev/ttyUSB0"},
                # {"motor_id": "motor2", "port": "/dev/ttyUSB1"}  # Add when available
            ]
            _motor_array = ESP32MotorArray(motor_configs)
            print("[tracking] Motor array initialized")
        except Exception as e:
            print(f"[tracking] Error initializing motor array: {e}")
            _motor_array = False  # Mark as failed to avoid retry
    return _motor_array if _motor_array else None


def _move_motors(delta_ha: float, delta_dec: float) -> None:
    """Move motors to compensate for HA and Dec deltas.
    
    Args:
        delta_ha: Hour angle difference in degrees (positive = east/forward)
        delta_dec: Declination difference in degrees (positive = north)
    """
    motors = _get_motor_array()
    if not motors or len(motors) == 0:
        print("[tracking] Warning: Motor array not available; cannot move motors")
        return
    
    # Convert degrees to steps
    ha_steps = int(round(delta_ha * STEPS_PER_DEGREE_HA))
    dec_steps = int(round(delta_dec * STEPS_PER_DEGREE_DEC))
    
    print(f"[tracking] Moving: HA delta={delta_ha:.4f}° ({ha_steps} steps), Dec delta={delta_dec:.4f}° ({dec_steps} steps)")
    
    try:
        # Move RA (Hour Angle) motor
        if ha_steps != 0:
            motor_ha = motors.get_by_id("motor1")
            motor_ha.move_steps(ha_steps, sps=800.0, forward=(ha_steps > 0))
            print(f"[tracking] Motor1 (HA) commanded: {ha_steps} steps")
        
        # Move Dec motor (if available)
        if dec_steps != 0 and len(motors) > 1:
            motor_dec = motors.get_by_id("motor2")
            motor_dec.move_steps(dec_steps, sps=800.0, forward=(dec_steps > 0))
            print(f"[tracking] Motor2 (Dec) commanded: {dec_steps} steps")
    except Exception as e:
        print(f"[tracking] Error moving motors: {e}")


def _set_polaris_alignment(location: dict) -> None:
    longitude = location.get('longitude')
    if longitude is None:
        print("[tracking] Warning: Longitude missing; cannot set Polaris alignment.")
        return
    polaris_ha = hour_angle(POLARIS_RA_DEG, longitude)
    set_telescope_coords(polaris_ha, POLARIS_DEC_DEG, source="polaris")


def trackCoordinates(name, ra, dec, mag):
    print(f"Tracking object: {name}, RA: {ra}, Dec: {dec}, Mag: {mag}")
    
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

    # Move motors to compensate for the deltas
    if abs(DeltaHA) > 0.001 or abs(DeltaDec) > 0.001:  # Only move if delta is significant
        _move_motors(DeltaHA, DeltaDec)
        # Update telescope state with new coordinates
        set_telescope_coords(TargetHA, TargetDec, source="tracking")
        print(f"[tracking] Telescope moved to HA={TargetHA:.4f}°, Dec={TargetDec:.4f}°")
    else:
        print(f"[tracking] Telescope already aligned (delta < 0.001°)")

    if ifAligned():
        _set_polaris_alignment(location)


def ifAligned():
    # placeholder, will link to a momentary button in the future
    # will return true if the telescope is polar aligned, otherwise false
    return True


