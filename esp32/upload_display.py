#!/usr/bin/env python3
from __future__ import annotations

import argparse
from PIL import Image
from esp32.interfaceESP32 import ESP32Connection, ESP32SerialConfig

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 160


def image_to_rgb565_bytes(img: Image.Image) -> bytes:
	img = img.convert("RGB").resize((DISPLAY_WIDTH, DISPLAY_HEIGHT))
	pixels = img.load()
	out = bytearray()
	for y in range(DISPLAY_HEIGHT):
		for x in range(DISPLAY_WIDTH):
			r, g, b = pixels[x, y]
			r5 = (r >> 3) & 0x1F
			g6 = (g >> 2) & 0x3F
			b5 = (b >> 3) & 0x1F
			val = (r5 << 11) | (g6 << 5) | b5
			high = (val >> 8) & 0xFF
			low = val & 0xFF
			out.append(high)
			out.append(low)
	return bytes(out)


if __name__ == "__main__":
	p = argparse.ArgumentParser()
	p.add_argument("image", help="Path to image file (will be resized to display)")
	p.add_argument("name", help="Remote filename to store on ESP32 (e.g. mypic.rgb)")
	p.add_argument("--port", help="Serial port (optional)", default=None)
	p.add_argument("--play", help="Play after upload", action="store_true")
	args = p.parse_args()

	img = Image.open(args.image)
	data = image_to_rgb565_bytes(img)

	cfg = ESP32SerialConfig()
	if args.port:
		cfg.port = args.port
	conn = ESP32Connection(cfg)
	print(f"Uploading {len(data)} bytes to {args.name}...")
	conn.upload_display_file(args.name, data)
	print("Upload complete.")
	if args.play:
		print("Playing on display...")
		conn.play_display_file(args.name)
		print("Play command sent.")
