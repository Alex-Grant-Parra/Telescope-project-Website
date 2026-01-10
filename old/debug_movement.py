#!/usr/bin/env python3
"""
Debug script to test step calculations and actual movement
"""

from esp32link import ESP32StepperController
import time

def debug_movement():
    """Debug the movement calculations and execution."""
    
    print("ESP32 Movement Debug Test")
    print("=" * 30)
    
    controller = ESP32StepperController(port='/dev/ttyUSB0', baudrate=115200)
    
    if not controller.connect():
        print("❌ Failed to connect")
        return
    
    print("✅ Connected!")
    
    # Enable motor
    controller.enable_motor()
    controller.home_position()
    
    print("\n=== Testing Step Calculations ===")
    
    # Test different step amounts
    test_degrees = [90, 180, 360]
    steps_per_rev = 200
    
    for degrees in test_degrees:
        calculated_steps = int((degrees / 360.0) * steps_per_rev)
        print(f"{degrees}° should be {calculated_steps} steps")
    
    print(f"\nUsing {steps_per_rev} steps per revolution")
    print(f"360° = {int((360 / 360.0) * steps_per_rev)} steps")
    
    print("\n=== Testing Small Movement First ===")
    
    # Test small movement first
    print("Testing 10 steps...")
    initial_status = controller.get_status()
    print(f"Initial position: {initial_status.get('Position', 0)}")
    
    controller.move_steps(10)
    controller.wait_for_movement_complete()
    
    after_small = controller.get_status()
    print(f"After 10 steps: {after_small.get('Position', 0)}")
    
    print("\n=== Testing 90° Movement ===")
    print("Moving 90° (50 steps)...")
    
    before_90 = controller.get_status()
    print(f"Before 90°: {before_90.get('Position', 0)}")
    
    # Calculate steps for 90 degrees
    steps_90 = int((90.0 / 360.0) * 200)  # Should be 50 steps
    print(f"Calculated steps for 90°: {steps_90}")
    
    controller.move_degrees(90.0)
    controller.wait_for_movement_complete()
    
    after_90 = controller.get_status()
    print(f"After 90°: {after_90.get('Position', 0)}")
    actual_moved = after_90.get('Position', 0) - before_90.get('Position', 0)
    print(f"Actually moved: {actual_moved} steps")
    
    print("\n=== Testing 360° Movement ===")
    print("Moving 360° (200 steps)...")
    
    before_360 = controller.get_status()
    print(f"Before 360°: {before_360.get('Position', 0)}")
    
    controller.move_degrees(360.0)
    print("Movement command sent, waiting...")
    controller.wait_for_movement_complete(timeout=120)  # Longer timeout
    
    after_360 = controller.get_status()
    print(f"After 360°: {after_360.get('Position', 0)}")
    actual_moved = after_360.get('Position', 0) - before_360.get('Position', 0)
    print(f"Actually moved: {actual_moved} steps")
    
    if actual_moved == 200:
        print("✅ Full revolution completed correctly!")
    else:
        print(f"⚠️ Expected 200 steps, got {actual_moved}")
    
    controller.disconnect()

if __name__ == "__main__":
    debug_movement()