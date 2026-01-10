#!/usr/bin/env python3
"""
ESP32 Motor Configuration Validator
Validates motor_config.json for syntax and configuration errors.
"""

import json
import sys
import os

def validate_motor_config(config_file="motor_config.json"):
    """Validate the motor configuration file"""
    
    if not os.path.exists(config_file):
        print(f"❌ Error: {config_file} not found!")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False
    
    print("✅ JSON syntax is valid")
    
    # Check required top-level keys
    if "motors" not in config:
        print("❌ Missing 'motors' array in configuration")
        return False
    
    motors = config["motors"]
    if not isinstance(motors, list):
        print("❌ 'motors' must be an array")
        return False
    
    if len(motors) == 0:
        print("❌ No motors defined in configuration")
        return False
    
    print(f"✅ Found {len(motors)} motor definitions")
    
    # Validate each motor
    enabled_count = 0
    motor_ids = set()
    used_pins = set()
    
    for i, motor in enumerate(motors):
        print(f"\n🔍 Validating motor {i+1}:")
        
        # Check required fields
        required_fields = ["id", "stepPin", "dirPin", "ledPin", "tmcUartTxPin", "enabled"]
        for field in required_fields:
            if field not in motor:
                print(f"  ❌ Missing required field: {field}")
                return False
        
        motor_id = motor["id"]
        if motor_id in motor_ids:
            print(f"  ❌ Duplicate motor ID: {motor_id}")
            return False
        motor_ids.add(motor_id)
        
        if motor.get("enabled", False):
            enabled_count += 1
            
            # Check pin assignments
            pins = [
                ("stepPin", motor["stepPin"]),
                ("dirPin", motor["dirPin"]), 
                ("ledPin", motor["ledPin"]),
                ("tmcUartTxPin", motor["tmcUartTxPin"])
            ]
            
            for pin_name, pin_num in pins:
                if not isinstance(pin_num, int) or pin_num < 0 or pin_num > 39:
                    print(f"  ❌ Invalid {pin_name}: {pin_num} (must be 0-39)")
                    return False
                
                if pin_num in used_pins:
                    print(f"  ❌ Pin {pin_num} ({pin_name}) already used by another motor")
                    return False
                used_pins.add(pin_num)
            
            # Check serial port
            serial_port = motor.get("serialPort", 2)
            if serial_port not in [0, 1, 2]:
                print(f"  ❌ Invalid serialPort: {serial_port} (must be 0, 1, or 2)")
                return False
            
            # Check TMC address
            tmc_addr = motor.get("tmcAddress", "0x00")
            if isinstance(tmc_addr, str):
                try:
                    addr_val = int(tmc_addr, 16)
                    if addr_val < 0 or addr_val > 255:
                        raise ValueError()
                except ValueError:
                    print(f"  ❌ Invalid tmcAddress: {tmc_addr} (must be hex string like '0x00')")
                    return False
            elif isinstance(tmc_addr, int):
                if tmc_addr < 0 or tmc_addr > 255:
                    print(f"  ❌ Invalid tmcAddress: {tmc_addr} (must be 0-255)")
                    return False
            
            print(f"  ✅ Motor '{motor_id}' configuration valid")
        else:
            print(f"  ⏭️ Motor '{motor_id}' disabled, skipping validation")
    
    if enabled_count == 0:
        print(f"\n❌ No enabled motors found! At least one motor must be enabled.")
        return False
    
    print(f"\n✅ Found {enabled_count} enabled motors")
    
    # Validate defaults section
    if "defaults" in config:
        defaults = config["defaults"]
        print(f"\n🔍 Validating defaults section:")
        
        if "microsteps" in defaults:
            ms = defaults["microsteps"]
            if not isinstance(ms, int) or ms <= 0:
                print(f"  ❌ Invalid microsteps: {ms} (must be positive integer)")
                return False
        
        if "current_mA" in defaults:
            current = defaults["current_mA"]
            if not isinstance(current, int) or current <= 0 or current > 3000:
                print(f"  ❌ Invalid current_mA: {current} (must be 1-3000)")
                return False
        
        if "max_accel" in defaults:
            accel = defaults["max_accel"]
            if not isinstance(accel, (int, float)) or accel <= 0:
                print(f"  ❌ Invalid max_accel: {accel} (must be positive number)")
                return False
        
        print(f"  ✅ Defaults section valid")
    
    print(f"\n🎉 Configuration validation successful!")
    print(f"📋 Summary:")
    print(f"  • Total motors: {len(motors)}")
    print(f"  • Enabled motors: {enabled_count}")
    print(f"  • Motor IDs: {', '.join(sorted(motor_ids))}")
    
    return True

if __name__ == "__main__":
    config_file = sys.argv[1] if len(sys.argv) > 1 else "motor_config.json"
    
    print(f"🔧 Validating ESP32 Motor Configuration: {config_file}")
    print("=" * 60)
    
    success = validate_motor_config(config_file)
    sys.exit(0 if success else 1)
