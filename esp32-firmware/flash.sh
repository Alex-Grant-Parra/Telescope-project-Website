#!/bin/bash

echo "🔌 Flashing firmware to ESP32..."

# Check if platformio is available
if ! command -v platformio &> /dev/null; then
  echo "❌ Error: 'platformio' command not found."
  echo "💡 Tip: Make sure your virtual environment is activated:"
  echo "    source ~/venv/bin/activate"
  exit 1
fi

# Optional: Check available memory
AVAILABLE_MEM=$(free -m | awk '/^Mem:/ { print $7 }')
if [ "$AVAILABLE_MEM" -lt 100 ]; then
  echo "⚠️ Warning: Low available memory (${AVAILABLE_MEM}MB). Compilation may fail."
fi

# Timestamped log
echo "$(date): Starting firmware upload..." >> flash_log.txt

# Run the upload with timeout and verbose output
timeout 90s platformio run -t upload -v
UPLOAD_STATUS=$?

if [ $UPLOAD_STATUS -eq 0 ]; then
  echo "✅ Flash successful."
  echo "📡 Launching serial monitor..."
  platformio device monitor
elif [ $UPLOAD_STATUS -eq 124 ]; then
  echo "⏱️ Upload timed out after 90 seconds. Check your ESP32 connection or port settings."
else
  echo "❌ Flash failed with exit code $UPLOAD_STATUS."
  echo "💡 Tip: Check your USB connection, board settings, or code for errors."
fi
