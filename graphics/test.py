#!/usr/bin/env python3
"""
Example: Upload and play a GIF on ESP32 display.

This demonstrates the simple API for working with GIFs:
- First run: uploads GIF frames to ESP32 and plays them
- Subsequent runs: uses cached frames (no re-upload)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from graphics.gif_player import upload_and_play_gif
from graphics.image_display import display_image, clear_display
from esp32.interfaceESP32 import ESP32Connection, ESP32Display
import time

from PIL import Image


# def image_to_rgb565_bytes(img: Image.Image, w: int, h: int) -> bytes:
# 	"""Convert PIL Image to RGB565 bytes."""
# 	img = img.convert("RGB").resize((w, h))
# 	pixels = img.load()
# 	out = bytearray()
# 	for y in range(h):
# 		for x in range(w):
# 			r, g, b = pixels[x, y]
# 			r5 = (r >> 3) & 0x1F
# 			g6 = (g >> 2) & 0x3F
# 			b5 = (b >> 3) & 0x1F
# 			val = (r5 << 11) | (g6 << 5) | b5
# 			out.append((val >> 8) & 0xFF)
# 			out.append(val & 0xFF)
# 	return bytes(out)


# def main() -> None:
# 	"""Upload and play test GIF."""
# 	gif_path = ROOT / "graphics" / "assets" / "test.gif"
# 	print(f"Processing {gif_path.name}...")
# 	gif_uuid = upload_and_play_gif(gif_path)

# if __name__ == "__main__":
# 	main()

# Display a PNG
# from graphics.image_display import display_image
# from pathlib import Path

conn = ESP32Connection()
display = ESP32Display(conn)
display.initialize()

# Set custom brightness
# 50% brightness
display_image(Path("graphics/assets/test.png"))
display.set_backlight(128)  
time.sleep(5)
clear_display()

# # Display at specific location
# display_image(Path("icon.jpg"), x=50, y=50, width=32, height=32)

# # Fill background then display image
# from graphics.image_display import clear_display
# clear_display("FF0000")  # Red background
# display_image(Path("photo.png"), x=10, y=10, width=108, height=140)