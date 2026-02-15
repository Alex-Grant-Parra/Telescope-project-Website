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
    except Exception as e:
        print(f"[telescope_state] Failed to write state: {e}")


def get_telescope_coords() -> Optional[Dict[str, float]]:
    """Return the last known telescope coordinates (RA/Dec) if available.
    
    Returns RA (right ascension) which is time-invariant, unlike hour angle.
    Use get_telescope_hour_angle() to get the current hour angle.
    """
    global _STATE_CACHE
    if _STATE_CACHE is None:
        _STATE_CACHE = _load_state_from_disk()
    if not _STATE_CACHE:
        return None
    
    # Handle backward compatibility: old state files may have 'hour_angle' instead of 'right_ascension'
    ra = _STATE_CACHE.get("right_ascension")
    if ra is None:
        # Legacy format - assume hour_angle was stored as RA (not ideal, but better than crashing)
        ra = _STATE_CACHE.get("hour_angle", 0.0)
        print(f"[telescope_state] Warning: Legacy state format detected. Migrating to RA storage.")
    
    return {
        "right_ascension": float(ra),
        "declination": float(_STATE_CACHE.get("declination", 0.0)),
    }


def set_telescope_coords(right_ascension: float, declination: float, source: str = "manual", hour_angle: float = None) -> None:
    """Persist new telescope coordinates (RA/Dec) and update in-memory cache.
    
    Args:
        right_ascension: Right Ascension in degrees (time-invariant)
        declination: Declination in degrees
        source: Source of the coordinate update
        hour_angle: Optional current hour angle (for live tracking display)
    """
    global _STATE_CACHE
    state = {
        "right_ascension": float(right_ascension),
        "declination": float(declination),
        "source": source,
        "updated_at": datetime.utcnow().isoformat(),
    }
    # Add hour angle if provided (for live tracking feedback)
    if hour_angle is not None:
        state["current_hour_angle"] = float(hour_angle)
    # Preserve slew_config if it exists
    if _STATE_CACHE and "slew_config" in _STATE_CACHE:
        state["slew_config"] = _STATE_CACHE["slew_config"]
    _STATE_CACHE = state
    _write_state_to_disk(state)


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

