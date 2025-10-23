from __future__ import annotations

import argparse
import os
import time

from esp32 import ESP32Motor, ESP32Config


def parse_args():
    p = argparse.ArgumentParser(description="Turn motor a specified number of degrees")
    p.add_argument("degrees", nargs="?", type=float, default=90.0, help="Degrees to turn (default 90)")
    p.add_argument("--duration", type=float, default=2.0, help="Duration in seconds for the move (default 2s)")
    p.add_argument("--port", type=str, default=os.environ.get("ESP32_PORT", "/dev/ttyUSB0"))
    return p.parse_args()


def main():
    args = parse_args()
    port = args.port
    cfg = ESP32Config(port=port, baudrate=115200)
    m = ESP32Motor(cfg)

    # Configurable via env
    FULL_STEPS_PER_REV = int(os.environ.get("FULL_STEPS_PER_REV", "200"))
    MICROSTEPS = int(os.environ.get("MICROSTEPS", "16"))

    # Compute steps for given degrees
    steps_per_rev = FULL_STEPS_PER_REV * MICROSTEPS
    steps_needed = int(round((args.degrees / 360.0) * steps_per_rev))
    sps = steps_needed / max(0.001, args.duration)

    print(f"Turning {args.degrees}°, steps_needed={steps_needed}, sps={sps:.2f}, duration={args.duration}s")

    try:
        m.enable(True)
        m.set_mode("stealth")
        m.set_current(500)
        m.set_microsteps(MICROSTEPS)
        m.set_accel(20000)
        m.set_direction(True)

        m.move_steps(steps=steps_needed, sps=sps, forward=True)

        # Wait until done, with timeout
        t0 = time.time()
        timeout = args.duration + 3.0
        while time.time() - t0 < timeout:
            st = m.status()
            if not st.get("enabled", False) or int(st.get("stepsRemaining", 0)) <= 0:
                break
            time.sleep(0.05)
    finally:
        try:
            m.stop()
            m.enable(False)
        except Exception:
            pass
        m.close()


if __name__ == "__main__":
    main()
