#!/usr/bin/env python3
"""
ESP32 Motor Controller Build and Upload Script
Validates configuration and builds/uploads the firmware.
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Exit code: {e.returncode}")
        if e.stdout:
            print(f"Output: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False

def main():
    print("🔧 ESP32 Motor Controller Build Script")
    print("=" * 50)
    
    # Step 1: Validate configuration
    print("\n📋 Step 1: Validating motor configuration")
    if not run_command("python validate_config.py", "Configuration validation"):
        print("❌ Fix configuration errors before building")
        return False
    
    # Step 2: Copy config to data directory
    print("\n📂 Step 2: Preparing file system")
    if not os.path.exists("data"):
        os.makedirs("data")
        print("✅ Created data directory")
    
    if not run_command("copy motor_config.json data\\ 2>nul || cp motor_config.json data/", "Copying config to data directory"):
        print("❌ Failed to copy configuration file")
        return False
    
    # Step 3: Build firmware
    print("\n🔨 Step 3: Building firmware")
    if not run_command("pio run", "Firmware compilation"):
        print("❌ Build failed - check for compilation errors")
        return False
    
    # Step 4: Upload file system (optional)
    upload_fs = input("\n📤 Upload file system to ESP32? (y/N): ").lower().strip()
    if upload_fs in ['y', 'yes']:
        if not run_command("pio run --target uploadfs", "File system upload"):
            print("⚠️ File system upload failed - you can upload manually later")
        else:
            print("✅ File system uploaded successfully")
    
    # Step 5: Upload firmware (optional)
    upload_fw = input("\n📤 Upload firmware to ESP32? (y/N): ").lower().strip()
    if upload_fw in ['y', 'yes']:
        if not run_command("pio run --target upload", "Firmware upload"):
            print("❌ Firmware upload failed")
            return False
        else:
            print("✅ Firmware uploaded successfully")
    
    print("\n🎉 Build process completed!")
    print("\n📋 Next steps:")
    if upload_fs != 'y' and upload_fw != 'y':
        print("  • Run 'pio run --target uploadfs' to upload file system")
        print("  • Run 'pio run --target upload' to upload firmware")
    print("  • Monitor serial output with 'pio device monitor'")
    print("  • Check boot messages for configuration loading status")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
