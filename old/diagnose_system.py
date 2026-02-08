#!/usr/bin/env python3
"""
Diagnostic script to verify ESP32 firmware and Python interface compatibility
"""
import sys
sys.path.append('/home/alex/Rpi5Client')
from esp32link import ESP32StepperController
import time

def test_esp32_firmware_integration():
    """Test all major functions to verify firmware/interface compatibility"""
    print("=" * 60)
    print("ESP32 FIRMWARE & PYTHON INTERFACE DIAGNOSTIC TEST")
    print("=" * 60)
    
    try:
        controller = ESP32StepperController()
        
        # Test 1: Connection
        print("\n1. Testing Connection...")
        if not controller.connect():
            print("❌ FAIL: Cannot connect to ESP32")
            return False
        print("✅ PASS: Connected successfully")
        
        # Test 2: Status retrieval
        print("\n2. Testing Status Retrieval...")
        status = controller.get_status()
        if not status:
            print("❌ FAIL: Cannot get status")
            return False
        print(f"✅ PASS: Status received: {status}")
        
        # Test 3: Motor enable/disable
        print("\n3. Testing Motor Enable/Disable...")
        if not controller.enable_motor():
            print("❌ FAIL: Cannot enable motor")
            return False
        
        status = controller.get_status()
        if not status.get('Enabled', False):
            print("❌ FAIL: Motor not showing as enabled in status")
            return False
        print("✅ PASS: Motor enabled successfully")
        
        if not controller.disable_motor():
            print("❌ FAIL: Cannot disable motor")
            return False
        
        status = controller.get_status()
        if status.get('Enabled', True):
            print("❌ FAIL: Motor still showing as enabled after disable")
            return False
        print("✅ PASS: Motor disabled successfully")
        
        # Test 4: Speed settings
        print("\n4. Testing Speed Configuration...")
        controller.enable_motor()
        speeds_to_test = [100, 1000, 5000, 10000]
        for speed in speeds_to_test:
            if not controller.set_speed(speed):
                print(f"❌ FAIL: Cannot set speed to {speed}μs")
                return False
            
            status = controller.get_status()
            if status.get('Speed') != speed:
                print(f"❌ FAIL: Speed not reflected in status. Set: {speed}, Got: {status.get('Speed')}")
                return False
        print("✅ PASS: All speed settings work correctly")
        
        # Test 5: Microstep settings
        print("\n5. Testing Microstep Configuration...")
        microsteps_to_test = [1, 2, 4, 8, 16, 32, 64, 256]
        for microsteps in microsteps_to_test:
            if not controller.set_microsteps(microsteps):
                print(f"❌ FAIL: Cannot set microsteps to {microsteps}")
                return False
            
            status = controller.get_status()
            if status.get('Microsteps') != microsteps:
                print(f"❌ FAIL: Microsteps not reflected in status. Set: {microsteps}, Got: {status.get('Microsteps')}")
                return False
        print("✅ PASS: All microstep settings work correctly")
        
        # Test 6: Movement types
        print("\n6. Testing Movement Type Configuration...")
        movement_types = ["STEALTH", "INTERPOLATED", "CONTINUOUS"]
        for movement_type in movement_types:
            if not controller.set_movement_type(movement_type):
                print(f"❌ FAIL: Cannot set movement type to {movement_type}")
                return False
            
            status = controller.get_status()
            if status.get('Movement') != movement_type:
                print(f"❌ FAIL: Movement type not reflected in status. Set: {movement_type}, Got: {status.get('Movement')}")
                return False
        print("✅ PASS: All movement types work correctly")
        
        # Test 7: Position tracking and small movements
        print("\n7. Testing Position Tracking...")
        controller.home_position()
        initial_status = controller.get_status()
        initial_position = initial_status.get('Position', 0)
        
        if initial_position != 0:
            print(f"❌ FAIL: Home position not set to 0. Got: {initial_position}")
            return False
        print("✅ PASS: Home position set correctly")
        
        # Test small movement
        print("\n8. Testing Small Movement...")
        controller.set_speed(1000)
        test_steps = 10
        
        if not controller.move_steps(test_steps):
            print("❌ FAIL: Cannot start movement")
            return False
        
        if not controller.wait_for_movement_complete(timeout=5.0):
            print("❌ FAIL: Movement did not complete")
            return False
        
        final_status = controller.get_status()
        final_position = final_status.get('Position', 0)
        
        if final_position != test_steps:
            print(f"❌ FAIL: Position tracking incorrect. Expected: {test_steps}, Got: {final_position}")
            return False
        print("✅ PASS: Small movement and position tracking work correctly")
        
        # Test 9: Emergency stop
        print("\n9. Testing Emergency Stop...")
        controller.move_steps(1000)  # Start a longer movement
        time.sleep(0.1)  # Let it start
        
        if not controller.emergency_stop():
            print("❌ FAIL: Emergency stop command failed")
            return False
        
        status = controller.get_status()
        if status.get('Moving', True):
            print("❌ FAIL: Motor still showing as moving after emergency stop")
            return False
        print("✅ PASS: Emergency stop works correctly")
        
        # Test 10: Calculate actual steps per revolution
        print("\n10. Testing Steps Per Revolution Calculation...")
        controller.home_position()
        controller.set_microsteps(16)
        controller.set_speed(500)  # Fast for testing
        
        # Test different step counts to find pattern
        test_movements = [200, 400, 800, 1600, 3200]
        results = {}
        
        for steps in test_movements:
            controller.home_position()
            initial_pos = controller.get_status().get('Position', 0)
            
            controller.move_steps(steps)
            controller.wait_for_movement_complete(timeout=30.0)
            
            final_pos = controller.get_status().get('Position', 0)
            actual_steps = final_pos - initial_pos
            results[steps] = actual_steps
            
            print(f"   Commanded: {steps} steps, Actual: {actual_steps} steps")
        
        # Check if commands match actual movement
        all_accurate = all(commanded == actual for commanded, actual in results.items())
        if all_accurate:
            print("✅ PASS: Step commands are accurately executed")
        else:
            print("❌ FAIL: Step command execution inaccurate")
            return False
        
        print("\n" + "=" * 60)
        print("OVERALL RESULT: ✅ ALL TESTS PASSED")
        print("ESP32 firmware and Python interface are working correctly!")
        print("=" * 60)
        
        # Provide calibration info
        print(f"\nCALIBRATION INFO:")
        print(f"- Step commands are executed 1:1 (no scaling needed)")
        print(f"- For exact rotations, you need to determine your motor's actual steps/revolution")
        print(f"- Standard NEMA17: 200 full steps/revolution")
        print(f"- With 16x microstepping: Motor moves in 1/16 step increments")
        print(f"- But ESP32 counts each microstep as 1 step command")
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Unexpected error: {e}")
        return False
        
    finally:
        try:
            controller.disable_motor()
            controller.disconnect()
        except:
            pass

if __name__ == "__main__":
    success = test_esp32_firmware_integration()
    sys.exit(0 if success else 1)