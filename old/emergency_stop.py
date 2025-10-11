#!/usr/bin/env python3
"""
Emergency Motor Stop Script
Use this to immediately stop the motor if it gets stuck during testing
"""

from esp32link import ESP32StepperController
import time

def emergency_stop_motor():
    """Immediately stop the motor and disable it."""
    print("🚨 EMERGENCY MOTOR STOP 🚨")
    
    try:
        controller = ESP32StepperController()
        if controller.connect():
            print("Connected to ESP32...")
            
            # Send emergency stop command
            result = controller.emergency_stop()
            print(f"Emergency stop command: {'SUCCESS' if result else 'FAILED'}")
            
            # Wait a moment
            time.sleep(0.5)
            
            # Disable motor
            result = controller.disable_motor()
            print(f"Motor disable command: {'SUCCESS' if result else 'FAILED'}")
            
            # Check status
            status = controller.get_status()
            if status:
                print(f"Motor status - Enabled: {status.get('Enabled')}, Moving: {status.get('Moving')}")
                print(f"Position: {status.get('Position')}, Target: {status.get('Target')}")
            else:
                print("Could not get motor status")
            
            controller.disconnect()
            print("Motor emergency stop completed ✅")
        else:
            print("❌ Could not connect to ESP32")
            
    except Exception as e:
        print(f"❌ Emergency stop failed: {e}")

if __name__ == "__main__":
    emergency_stop_motor()