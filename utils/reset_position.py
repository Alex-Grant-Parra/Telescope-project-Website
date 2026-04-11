"""Reset telescope coordinates to a known position or to the next target"""

from utils.telescope_state import set_telescope_coords

def reset_to_zero():
    """Reset telescope position to RA=0, Dec=0 (home position)"""
    set_telescope_coords(0.0, 0.0, source="manual_reset")
    print("[reset] Telescope position reset to RA=0°, Dec=0°")

def reset_to_target(ra, dec):
    """Reset telescope position to match target (use when telescope is manually pointed)
    
    Args:
        ra: Right ascension in degrees
        dec: Declination in degrees
    """
    set_telescope_coords(float(ra), float(dec), source="manual_reset")
    print(f"[reset] Telescope position reset to RA={ra}°, Dec={dec}°")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        ra = float(sys.argv[1])
        dec = float(sys.argv[2])
        reset_to_target(ra, dec)
    else:
        reset_to_zero()
