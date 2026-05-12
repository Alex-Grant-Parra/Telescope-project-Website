"""GIF upload and playback functionality.

High-level interface for uploading GIFs to ESP32 and playing them back,
with automatic caching.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from esp32.interfaceESP32 import ESP32Connection, ESP32Display
from graphics import gif_storage
from PIL import Image, ImageSequence


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


def upload_and_play_gif(
	gif_path: Path,
	max_frames: int | None = None,
	frame_step: int = 1,
	upload_timeout: float = 25.0,
	upload_retries: int = 3,
	format_storage: bool = True,
) -> str:
	"""
	Upload a GIF to ESP32 and play it.
	
	On first upload: uploads all frames and caches them.
	On subsequent calls: uses cached frames, skips upload.
	
	Returns: UUID of the GIF
	"""
	conn = None
	display = None
	try:
		print("Connecting to ESP32...")
		conn = ESP32Connection()
		display = ESP32Display(conn)
		display.initialize()
		
		# Check if GIF is already cached
		gif_uuid, gif_info = gif_storage.get_or_create_gif_uuid(gif_path)
		is_cached = gif_storage.is_gif_cached(gif_path)
		
		if is_cached:
			print(f"✓ GIF already uploaded (UUID: {gif_uuid})")
			print(f"  Using {len(gif_info['frames'])} cached frames")
			frames = gif_info["frames"]
			durations = gif_info.get("durations", [1.0] * len(frames))
		else:
			print(f"→ Uploading new GIF (UUID: {gif_uuid})")
			
			if format_storage:
				print("  Formatting ESP32 display storage...")
				display.format_storage()
			
			img = Image.open(gif_path)
			frames = []
			durations = []
			frame_idx = 0
			
			for frame in ImageSequence.Iterator(img):
				if frame_idx % frame_step != 0:
					frame_idx += 1
					continue
				if max_frames is not None and len(frames) >= max_frames:
					break
				
				duration = frame.info.get("duration", 100) / 1000.0
				durations.append(duration)
				
				# Convert frame to RGB565
				raw = image_to_rgb565_bytes(frame, ESP32Display.WIDTH, ESP32Display.HEIGHT)
				
				name = f"{gif_path.stem}_{frame_idx}.rgb"
				print(f"  Uploading frame {frame_idx} ({len(raw)} bytes)...")
				
				# Upload with retries
				last_exc = None
				for attempt in range(1, upload_retries + 1):
					try:
						conn.upload_display_file(name, raw, timeout=upload_timeout)
						last_exc = None
						gif_storage.record_uploaded_frame(gif_path, name)
						break
					except Exception as exc:
						last_exc = exc
						if attempt == upload_retries:
							break
						print(f"    Upload failed (attempt {attempt}/{upload_retries}): {exc}")
						print("    Reconnecting and retrying...")
						try:
							conn.close()
						except Exception:
							pass
						time.sleep(0.5)
						conn = ESP32Connection()
						display = ESP32Display(conn)
						display.initialize()
				
				if last_exc is not None:
					raise last_exc
				
				frames.append(name)
				frame_idx += 1
			
			# Store durations
			gif_storage.record_frame_durations(gif_path, durations)
		
		# Play the GIF
		print("Playing from ESP32...")
		display.set_backlight(255)
		display.power(True)
		time.sleep(0.2)
		
		for idx, name in enumerate(frames):
			conn.play_display_file(name, x=0, y=0, w=ESP32Display.WIDTH, h=ESP32Display.HEIGHT)
			sleep_time = durations[idx] if idx < len(durations) else 1.0
			time.sleep(sleep_time)
		
		print("Done.")
		return gif_uuid
		
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


def play_stored_gif_by_uuid(uuid_str: str) -> None:
	"""Play a stored GIF by UUID without re-uploading."""
	gif_info = gif_storage.get_gif_by_uuid(uuid_str)
	
	if not gif_info:
		print(f"GIF with UUID {uuid_str} not found.")
		return
	
	conn = None
	display = None
	try:
		print(f"Playing GIF (UUID: {uuid_str})")
		print(f"  Path: {gif_info['original_path']}")
		
		conn = ESP32Connection()
		display = ESP32Display(conn)
		display.initialize()
		
		# Ensure backlight is on
		display.set_backlight(255)
		display.power(True)
		time.sleep(0.2)
		
		frames = gif_info["frames"]
		durations = gif_info.get("durations", [1.0] * len(frames))
		
		print(f"Playing {len(frames)} frames from ESP32...")
		for idx, name in enumerate(frames):
			conn.play_display_file(name, x=0, y=0, w=ESP32Display.WIDTH, h=ESP32Display.HEIGHT)
			sleep_time = durations[idx] if idx < len(durations) else 1.0
			time.sleep(sleep_time)
		
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
