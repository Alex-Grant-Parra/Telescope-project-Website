import os
import json
from typing import Optional

LIVEVIEW_STATE_FILE = "liveview_state.json"

def load_liveview_state() -> bool:
    """Load live view state from file; defaults to False if missing or unreadable."""
    if os.path.exists(LIVEVIEW_STATE_FILE):
        try:
            with open(LIVEVIEW_STATE_FILE, 'r') as f:
                state = json.load(f)
                return bool(state.get("enabled", False))
        except Exception:
            pass
    return False


def save_liveview_state(enabled: bool) -> None:
    """Persist live view state to file."""
    try:
        with open(LIVEVIEW_STATE_FILE, 'w') as f:
            json.dump({"enabled": bool(enabled)}, f)
    except Exception:
        pass


def is_liveview_enabled() -> bool:
    """Check current live view state by reading the state file."""
    return load_liveview_state()
