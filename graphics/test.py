#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from esp32.interfaceESP32 import ESP32Connection, ESP32Display
from graphics.engine import GraphicsEngine
from PIL import Image, ImageSequence
import time


def image_to_rgb565_bytes(img: Image.Image, w: int, h: int) -> bytes:
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


def main() -> None:
	conn = None
	display = None
	try:
		print("Connecting to ESP32...")
		conn = ESP32Connection()
		display = ESP32Display(conn)
		engine = GraphicsEngine(display, auto_initialize=True)

		gif_path = ROOT / "graphics" / "assets" / "test.gif"
		print(f"Uploading frames from {gif_path.name} to ESP32...")
		img = Image.open(gif_path)
		frames = []
		durations = []
		for i, frame in enumerate(ImageSequence.Iterator(img)):
			duration = frame.info.get("duration", 100) / 1000.0
			durations.append(duration)
			raw = image_to_rgb565_bytes(frame, ESP32Display.WIDTH, ESP32Display.HEIGHT)
			name = f"{gif_path.stem}_{i}.rgb"
			print(f"  Uploading frame {i} as {name} ({len(raw)} bytes)...")
			conn.upload_display_file(name, raw)
			frames.append(name)

		print("Upload complete. Playing from ESP32...")
		loops = 1
		for loop in range(loops):
			for idx, name in enumerate(frames):
				conn.play_display_file(name, x=0, y=0, w=ESP32Display.WIDTH, h=ESP32Display.HEIGHT)
				time.sleep(durations[idx])
		print("Done.")
	except Exception as exc:
		print(f"Error: {exc}")
		raise
	finally:
		if display is not None:
			try:
				display.clear("000000")
				display.set_backlight(0)
			except Exception:
				pass
		if conn is not None:
			try:
				conn.close()
			except Exception:
				pass


if __name__ == "__main__":
	main()
