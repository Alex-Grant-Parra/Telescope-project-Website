#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from esp32.interfaceESP32 import ESP32Connection, ESP32Display
from graphics.engine import GraphicsEngine


def main() -> None:
	conn = None
	display = None
	try:
		print("Connecting to ESP32...")
		conn = ESP32Connection()
		display = ESP32Display(conn)
		engine = GraphicsEngine(display, auto_initialize=True)

		gif_path = ROOT / "graphics" / "assets" / "test.gif"
		print(f"Playing {gif_path.name}...")
		engine.clear("000000")
		engine.play_gif(gif_path, x=0, y=0, scale=1.0, loops=1, clear_between_frames=True)
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
