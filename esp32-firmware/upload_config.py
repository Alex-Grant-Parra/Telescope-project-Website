# ESP32 Motor Configuration File Upload Script
# This script uploads the motor_config.json file to the ESP32 SPIFFS filesystem

import os
import shutil

# Ensure the data directory exists for PlatformIO
data_dir = "data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)
    print(f"Created {data_dir} directory")

# Copy the configuration file to the data directory
config_file = "motor_config.json"
if os.path.exists(config_file):
    shutil.copy(config_file, os.path.join(data_dir, config_file))
    print(f"Copied {config_file} to {data_dir}/")
    print("Now run 'pio run --target uploadfs' to upload the file system to ESP32")
else:
    print(f"Error: {config_file} not found!")
    print("Make sure motor_config.json exists in the current directory")
