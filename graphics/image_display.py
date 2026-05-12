"""Static image display functionality.

High-level interface for displaying static images on ESP32 with optional compression.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from esp32.interfaceESP32 import ESP32Connection, ESP32Display
from PIL import Image


def image_to_rgb565_bytes(img: Image.Image, w: int, h: int) -> bytes:
	"""Convert PIL Image to RGB565 bytes."""
	img = img.convert("RGB").resize((w, h))
	pixels = img.load()
	out = bytearray()
	for y in range(h):
		for x in range(w):
			r, g, b = pixels[x, y]
			r5 = (r >> 3) & 0x1F
			g6 = (g >> 2) & 0x3F
			b5 = (b >> 3) & 0x1F
			val = (r5 << 11) | (g6 << 5) | b5
			out.append((val >> 8) & 0xFF)
			out.append(val & 0xFF)
	return bytes(out)


def display_image(
	image_path: Path,
	x: int = 0,
	y: int = 0,
	width: int = 128,
	height: int = 160,
	compressed: bool = False,
	compress_level: int = 6,
) -> None:
	"""
	Display a static image on ESP32 screen.
	
	Args:
		image_path: Path to image file (PNG, JPG, GIF, etc)
		x, y: Position on screen (default: top-left corner)
		width, height: Display dimensions (default: 128x160 full screen)
		compressed: Use compression for faster transfer (default: False)
		compress_level: Compression level 0-9 for zlib (default: 6)
		
	Example:
		from pathlib import Path
		from graphics.image_display import display_image
		
		image_path = Path("graphics/assets/test.gif")
		display_image(image_path)  # Display full-screen
		display_image(image_path, x=16, y=32, width=96, height=96)  # Smaller, positioned
	"""
	conn = None
	display = None
	try:
		print(f"Displaying image: {image_path.name}")
		print(f"  Position: ({x}, {y})")
		print(f"  Size: {width}x{height}")
		if compressed:
			print(f"  Compression: level {compress_level}")
		
		conn = ESP32Connection()
		display = ESP32Display(conn)
		display.initialize()
		
		# Load and convert image
		img = Image.open(image_path)
		rgb565_data = image_to_rgb565_bytes(img, width, height)
		
		# Send to display
		if compressed:
			display.blit_rgb565_compressed(x, y, width, height, rgb565_data, compress_level)
			print(f"  Compressed size: {len(rgb565_data)} bytes")
		else:
			display.blit_rgb565(x, y, width, height, rgb565_data)
			print(f"  Uncompressed size: {len(rgb565_data)} bytes")
		
		print("✓ Image displayed!")
		
	finally:
		if conn is not None:
			try:
				conn.close()
			except Exception:
				pass


def clear_display(color: str = "000000") -> None:
	"""
	Clear the display with a solid color.
	
	Args:
		color: Hex color code (default: "000000" for black)
		
	Example:
		from graphics.image_display import clear_display
		clear_display("FFFFFF")  # Clear with white
	"""
	conn = None
	display = None
	try:
		conn = ESP32Connection()
		display = ESP32Display(conn)
		display.initialize()
		display.clear(color)
		print(f"✓ Display cleared with color #{color}")
	finally:
		if conn is not None:
			try:
				conn.close()
			except Exception:
				pass
