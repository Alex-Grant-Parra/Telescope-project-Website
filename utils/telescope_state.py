import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

TELESCOPE_STATE_FILE = os.path.join("config", "telescope_state.json")

_STATE_CACHE: Optional[Dict[str, Any]] = None


def _load_state_from_disk() -> Optional[Dict[str, Any]]:
    if not os.path.exists(TELESCOPE_STATE_FILE):
        return None
    try:
        with open(TELESCOPE_STATE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[telescope_state] Failed to read state: {e}")
        return None


def _write_state_to_disk(state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(TELESCOPE_STATE_FILE), exist_ok=True)
    try:
        with open(TELESCOPE_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
            f.flush()  # Force write to disk
            os.fsync(f.fileno())  # Ensure OS writes to disk
        # print(f"[telescope_state] State written to disk")  # Uncomment for debugging
    except Exception as e:
        print(f"[telescope_state] Failed to write state: {e}")


def get_telescope_coords() -> Optional[Dict[str, float]]:
    """Return the current telescope coordinates (RA/Dec) if available.
    
    Returns RA (right ascension) which is time-invariant, unlike hour angle.
    Use get_telescope_hour_angle() to get the current hour angle.
    """
    global _STATE_CACHE
    if _STATE_CACHE is None:
        _STATE_CACHE = _load_state_from_disk()
    if not _STATE_CACHE:
        return None
    
    # Handle backward compatibility: old state files may have 'right_ascension'/'declination'
    current_ra = _STATE_CACHE.get("current_right_ascension")
    current_dec = _STATE_CACHE.get("current_declination")
    
    if current_ra is None:
        # Legacy format - try old field names
        current_ra = _STATE_CACHE.get("right_ascension")
        if current_ra is not None:
            print(f"[telescope_state] Warning: Migrating from legacy RA/Dec format to current_RA/current_Dec.")
        else:
            # Ultra-legacy format
            current_ra = _STATE_CACHE.get("hour_angle", 0.0)
            print(f"[telescope_state] Warning: Very old state format detected, using hour_angle as RA.")
    
    if current_dec is None:
        current_dec = _STATE_CACHE.get("declination", 0.0)
    
    return {
        "right_ascension": float(current_ra),
        "declination": float(current_dec),
    }


def get_target_coords() -> Optional[Dict[str, float]]:
    """Return the target telescope coordinates (RA/Dec) if available.
    
    Returns the target position the telescope is aiming for.
    """
    global _STATE_CACHE
    if _STATE_CACHE is None:
        _STATE_CACHE = _load_state_from_disk()
    if not _STATE_CACHE:
        return None
    
    target_ra = _STATE_CACHE.get("target_right_ascension")
    target_dec = _STATE_CACHE.get("target_declination")
    
    # If no target is set, use current position as target
    if target_ra is None or target_dec is None:
        return get_telescope_coords()
    
    return {
        "right_ascension": float(target_ra),
        "declination": float(target_dec),
    }


def set_telescope_coords(right_ascension: float, declination: float, source: str = "manual", hour_angle: float = None) -> None:
    """Persist the current telescope coordinates (RA/Dec) and update in-memory cache.
    
    This updates the CURRENT position of the telescope, not the target.
    
    Args:
        right_ascension: Right Ascension in degrees (time-invariant)
        declination: Declination in degrees
        source: Source of the coordinate update
        hour_angle: Optional current hour angle (for live tracking display)
    """
    global _STATE_CACHE
    if _STATE_CACHE is None:
        _STATE_CACHE = _load_state_from_disk() or {}
    
    state = _STATE_CACHE.copy()
    state.update({
        "current_right_ascension": float(right_ascension),
        "current_declination": float(declination),
        "source": source,
        "updated_at": datetime.utcnow().isoformat(),
    })
    # Add hour angle if provided (for live tracking feedback)
    if hour_angle is not None:
        state["current_hour_angle"] = float(hour_angle)
    
    _STATE_CACHE = state
    _write_state_to_disk(state)
    print(f"[telescope_state] Current coords set: RA={right_ascension:.4f}°, Dec={declination:.4f}°")


def set_target_coords(right_ascension: float, declination: float, source: str = "manual") -> None:
    """Persist the target telescope coordinates (RA/Dec) and update in-memory cache.
    
    This updates the TARGET position the telescope is aiming for.
    
    Args:
        right_ascension: Target Right Ascension in degrees (time-invariant)
        declination: Target Declination in degrees
        source: Source of the target update
    """
    global _STATE_CACHE
    if _STATE_CACHE is None:
        _STATE_CACHE = _load_state_from_disk() or {}
    
    state = _STATE_CACHE.copy()
    state.update({
        "target_right_ascension": float(right_ascension),
        "target_declination": float(declination),
        "updated_at": datetime.utcnow().isoformat(),
    })
    
    _STATE_CACHE = state
    _write_state_to_disk(state)
    print(f"[telescope_state] Target coords set: RA={right_ascension:.4f}°, Dec={declination:.4f}°")


def update_hour_angle() -> Optional[float]:
    """Update the current hour angle to reflect Earth's rotation.
    
    This keeps RA constant while recalculating HA based on current time and location.
    Returns the updated hour angle or None if it couldn't be calculated.
    """
    from utils.Tools import hour_angle as calculate_hour_angle
    from utils.location import get_current_location
    
    global _STATE_CACHE
    if _STATE_CACHE is None:
        _STATE_CACHE = _load_state_from_disk() or {}
    
    # Get current RA (which is time-invariant)
    current_ra = _STATE_CACHE.get("current_right_ascension", 0.0)
    
    if current_ra == 0.0:
        return None
    
    # Get observer location
    location = get_current_location()
    if location is None:
        return None
    
    longitude = location.get('longitude')
    if longitude is None:
        return None
    
    # Recalculate hour angle based on current time
    current_ha = calculate_hour_angle(current_ra, longitude)
    
    # Update state with new hour angle
    state = _STATE_CACHE.copy()
    state["current_hour_angle"] = float(current_ha)
    state["updated_at"] = datetime.utcnow().isoformat()
    
    _STATE_CACHE = state
    _write_state_to_disk(state)
    
    return current_ha


def get_slew_config() -> Dict[str, float]:
    """Return slewing configuration (speeds and thresholds)."""
    global _STATE_CACHE
    if _STATE_CACHE is None:
        _STATE_CACHE = _load_state_from_disk()
    if not _STATE_CACHE:
        # Return defaults if no config found
        return {
            "slew_speed_sps": 1200.0,
            "refine_speed_sps": 150.0,
            "tracking_speed_sps": 6.7,
            "slew_threshold_degrees": 1.0,
            "center_threshold_degrees": 0.1,
            "centered_threshold_degrees": 0.01,
            "ra_gear_ratio": 360.0,
            "dec_gear_ratio": 144.0,
        }
    config = _STATE_CACHE.get("slew_config", {})
    # Return with defaults for any missing keys
    return {
        "slew_speed_sps": float(config.get("slew_speed_sps", 1200.0)),
        "refine_speed_sps": float(config.get("refine_speed_sps", 150.0)),
        "tracking_speed_sps": float(config.get("tracking_speed_sps", 6.7)),
        "slew_threshold_degrees": float(config.get("slew_threshold_degrees", 1.0)),
        "center_threshold_degrees": float(config.get("center_threshold_degrees", 0.1)),
        "centered_threshold_degrees": float(config.get("centered_threshold_degrees", 0.01)),
        "ra_gear_ratio": float(config.get("ra_gear_ratio", 360.0)),
        "dec_gear_ratio": float(config.get("dec_gear_ratio", 144.0)),
    }

