from __future__ import annotations

import os
import time

from esp32.esp32 import ESP32Motor, ESP32Config


def main():
    # Adjust if your device path differs
    port = os.environ.get("ESP32_PORT", "/dev/ttyUSB0")
    cfg = ESP32Config(port=port, baudrate=115200)
    m = ESP32Motor(cfg)

    # Motor/microstep assumptions (overridable via environment)
    FULL_STEPS_PER_REV = int(os.environ.get("FULL_STEPS_PER_REV", "200"))   # typical NEMA17
    MICROSTEPS = int(os.environ.get("MICROSTEPS", "16"))                   # must match driver setting
    DURATION_SEC = 5.0

    steps = FULL_STEPS_PER_REV * MICROSTEPS  # 360 degrees worth of microsteps
    sps = steps / DURATION_SEC                # steps per second for ~5s duration

    print(f"FULL_STEPS_PER_REV={FULL_STEPS_PER_REV}, MICROSTEPS={MICROSTEPS}")
    print(f"Commanding steps={steps} microsteps total -> sps={sps:.2f} steps/sec for duration={DURATION_SEC}s")

    try:
        # Basic setup for a quiet single revolution
        m.enable(True)
        m.set_mode("stealth")   # or "spread" for more torque
        m.set_current(500)       # mA, tune for your motor
        m.set_microsteps(MICROSTEPS)
        m.set_accel(20000)       # fast ramp to reach target speed quickly
        m.set_direction(True)    # forward

        # Command one full revolution in ~5 seconds
        m.move_steps(steps=steps, sps=sps, forward=True)

        # Optional: wait until done (poll status)
        t0 = time.time()
        while time.time() - t0 < DURATION_SEC + 3:
            st = m.status()
            if not st.get("enabled", False) or int(st.get("stepsRemaining", 0)) <= 0:
                break
            time.sleep(0.1)
    finally:
        # Ensure motor is stopped and interface closed
        try:
            m.stop()
            m.enable(False)
        except Exception:
            pass
        m.close()


if __name__ == "__main__":
    main()
