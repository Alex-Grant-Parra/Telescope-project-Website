#!/usr/bin/env python3
"""
Debug script to isolate ESP32 connection issues.
"""

import serial
import time
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

def debug_connection():
    """Debug the ESP32 connection step by step."""
    
    print("=== ESP32 Connection Debug ===")
    
    try:
        print("Step 1: Opening serial port /dev/ttyUSB0...")
        ser = serial.Serial(
            port='/dev/ttyUSB0',
            baudrate=115200,
            timeout=2.0,
            write_timeout=2.0
        )
        print("✅ Serial port opened successfully")
        
        print("Step 2: Waiting for ESP32 to initialize (2 seconds)...")
        time.sleep(2)
        
        print("Step 3: Clearing buffers...")
        ser.flushInput()
        ser.flushOutput()
        
        print("Step 4: Sending STATUS command...")
        ser.write(b'STATUS\n')
        ser.flush()
        
        print("Step 5: Reading response...")
        response = ser.readline()
        print(f"Raw response: {repr(response)}")
        
        if response:
            decoded = response.decode('utf-8').strip()
            print(f"Decoded response: '{decoded}'")
            
            if decoded.startswith("STATUS:"):
                print("✅ Got valid STATUS response!")
                return True
            else:
                print("❌ Response doesn't start with 'STATUS:'")
                return False
        else:
            print("❌ No response received")
            return False
            
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False
    finally:
        try:
            ser.close()
            print("Serial port closed")
        except:
            pass

def debug_with_esp32link():
    """Test using the actual ESP32StepperController class."""
    print("\n=== Testing ESP32StepperController Class ===")
    
    from esp32link import ESP32StepperController
    
    # Enable debug logging for the class
    logging.getLogger('esp32link').setLevel(logging.DEBUG)
    
    controller = ESP32StepperController(port='/dev/ttyUSB0', baudrate=115200, timeout=2.0)
    
    print("Attempting connection...")
    success = controller.connect()
    
    if success:
        print("✅ Connection successful!")
        
        # Test a few commands
        print("Testing enable command...")
        result = controller.enable_motor()
        print(f"Enable result: {result}")
        
        print("Testing status command...")
        status = controller.get_status()
        print(f"Status: {status}")
        
        controller.disconnect()
    else:
        print("❌ Connection failed")
    
    return success

if __name__ == "__main__":
    print("Testing direct serial communication...")
    direct_success = debug_connection()
    
    if direct_success:
        print("\n" + "="*50)
        print("Direct communication works! Testing class...")
        class_success = debug_with_esp32link()
        
        if not class_success:
            print("\n❌ Class-based communication failed")
            print("There might be an issue with the ESP32StepperController implementation")
    else:
        print("\n❌ Direct communication failed")
        print("Check ESP32 connection and firmware")