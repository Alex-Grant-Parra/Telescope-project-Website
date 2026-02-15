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
    """Return the last known telescope coordinates (HA/Dec) if available."""
    global _STATE_CACHE
    if _STATE_CACHE is None:
        _STATE_CACHE = _load_state_from_disk()
    if not _STATE_CACHE:
        return None
    return {
        "hour_angle": float(_STATE_CACHE.get("hour_angle", 0.0)),
        "declination": float(_STATE_CACHE.get("declination", 0.0)),
    }


def set_telescope_coords(hour_angle: float, declination: float, source: str = "manual") -> None:
    """Persist new telescope coordinates (HA/Dec) and update in-memory cache."""
    global _STATE_CACHE
    state = {
        "hour_angle": float(hour_angle),
        "declination": float(declination),
        "source": source,
        "updated_at": datetime.utcnow().isoformat(),
    }
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
            "slew_speed_sps": 800.0,
            "refine_speed_sps": 400.0,
            "tracking_speed_sps": 100.0,
            "slew_threshold_degrees": 1.0,
            "center_threshold_degrees": 0.1,
            "centered_threshold_degrees": 0.01,
        }
    config = _STATE_CACHE.get("slew_config", {})
    # Return with defaults for any missing keys
    return {
        "slew_speed_sps": float(config.get("slew_speed_sps", 800.0)),
        "refine_speed_sps": float(config.get("refine_speed_sps", 400.0)),
        "tracking_speed_sps": float(config.get("tracking_speed_sps", 100.0)),
        "slew_threshold_degrees": float(config.get("slew_threshold_degrees", 1.0)),
        "center_threshold_degrees": float(config.get("center_threshold_degrees", 0.1)),
        "centered_threshold_degrees": float(config.get("centered_threshold_degrees", 0.01)),
    }

