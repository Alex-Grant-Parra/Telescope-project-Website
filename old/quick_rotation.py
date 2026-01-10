#!/usr/bin/env python3
from esp32link import ESP32StepperController

with ESP32StepperController() as controller:
    for i in range(0, 5):
        # Check current status and configuration
        status = controller.get_status()
        print(f"Initial status: {status}")
        
        controller.enable_motor()
        controller.set_speed(1000)  # Normal speed (1000μs)
        controller.set_microsteps(256)  # Ensure consistent microstep setting
        
        steps_per_revolution = 200  # One full revolution
        controller.move_steps(steps_per_revolution)  # One revolution clockwise
        controller.wait_for_movement_complete()
        
        final_status = controller.get_status()
        print(f"Final status: {final_status}")
        print("One rotation complete!")