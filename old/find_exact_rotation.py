#!/usr/bin/env python3
"""
Quick test to find exact steps per revolution
"""
import sys
sys.path.append('/home/alex/Rpi5Client')
from esp32link import ESP32StepperController

# Based on your observations:
# 1024 steps = ~2/3 rotation (240°)  
# 1600 steps = just short of full rotation
# So full rotation should be around 1650-1700 steps

test_values = [1650, 1660, 1670, 1680, 1690, 1700]

with ESP32StepperController() as controller:
    controller.enable_motor()
    controller.set_speed(1000)
    controller.set_microsteps(16)
    
    print("Testing step values around the expected range...")
    print("Watch your motor and note which value gives EXACTLY one full rotation")
    print()
    
    for steps in test_values:
        controller.home_position()
        print(f"Testing {steps} steps - press Enter when ready")
        input()
        
        controller.move_steps(steps)
        controller.wait_for_movement_complete()
        
        print(f"  Completed {steps} steps")
        print("  Did this complete exactly one full rotation?")
        print()
        
    print("Based on which value gave exactly one rotation,")
    print("update your quick_rotation.py with that number.")