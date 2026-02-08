#!/usr/bin/env python3
"""
Calibration script to find exact steps per revolution for your motor setup
"""
import sys
sys.path.append('/home/alex/Rpi5Client')
from esp32link import ESP32StepperController

def calibrate_steps_per_revolution():
    """Find exact steps needed for one complete revolution"""
    print("MOTOR CALIBRATION - Finding exact steps per revolution")
    print("=" * 60)
    
    with ESP32StepperController() as controller:
        controller.enable_motor()
        controller.set_speed(1000)  # Normal speed
        controller.set_microsteps(16)  # Your current setting
        controller.home_position()
        
        print("Testing different step counts to find exact revolution...")
        print("Mark the motor's starting position and watch for complete rotations")
        print()
        
        # Test step counts around theoretical values
        test_steps = [
            200,   # Full steps only
            800,   # 4x microstepping  
            1600,  # 8x microstepping
            3200,  # 16x microstepping (theoretical)
            1500, 1550, 1600, 1650, 1700, 1750, 1800  # Fine tuning range
        ]
        
        for steps in test_steps:
            controller.home_position()
            print(f"Testing {steps} steps...")
            
            controller.move_steps(steps)
            controller.wait_for_movement_complete()
            
            final_status = controller.get_status()
            actual_position = final_status['Position']
            
            input(f"  Motor moved {actual_position} steps. Is this exactly one revolution? (Press Enter to continue)")
            
            response = input("  Was this exactly one full revolution? (y/n): ").lower()
            if response == 'y':
                print(f"\n✅ FOUND: {steps} steps = exactly one revolution")
                print(f"Degrees per step: {360.0/steps:.6f}°")
                print(f"Steps per degree: {steps/360.0:.6f}")
                
                # Update quick_rotation.py with correct value
                with open('/home/alex/Rpi5Client/quick_rotation_calibrated.py', 'w') as f:
                    f.write(f"""#!/usr/bin/env python3
from esp32link import ESP32StepperController

# Calibrated value: {steps} steps per revolution
STEPS_PER_REVOLUTION = {steps}

with ESP32StepperController() as controller:
    controller.enable_motor()
    controller.set_speed(1000)
    controller.set_microsteps(16)
    
    print(f"Rotating exactly one revolution ({steps} steps)...")
    controller.move_steps(STEPS_PER_REVOLUTION)
    controller.wait_for_movement_complete()
    print("Exact one rotation complete!")
""")
                print(f"\n📝 Saved calibrated script as 'quick_rotation_calibrated.py'")
                return steps
        
        print("\n❌ Exact revolution not found in test range")
        print("Try manually testing step counts around the closest value")
        return None

if __name__ == "__main__":
    calibrate_steps_per_revolution()