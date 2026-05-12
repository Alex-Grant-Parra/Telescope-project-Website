#!/usr/bin/env python3

from __future__ import annotations

import sys
import os
from pathlib import Path
import uuid
import hashlib
import json
from datetime import datetime


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from esp32.interfaceESP32 import ESP32Connection, ESP32Display
from graphics.engine import GraphicsEngine
from PIL import Image, ImageSequence
import time


METADATA_FILE = ROOT / ".astra_uploads.json"


def compute_file_hash(file_path: Path) -> str:
	"""Compute SHA256 hash of a file."""
	sha256_hash = hashlib.sha256()
	with open(file_path, "rb") as f:
		for byte_block in iter(lambda: f.read(4096), b""):
			sha256_hash.update(byte_block)
	return sha256_hash.hexdigest()


def load_upload_metadata() -> dict:
	"""Load upload metadata from disk."""
	if METADATA_FILE.exists():
		try:
			with open(METADATA_FILE, "r") as f:
				return json.load(f)
		except Exception as e:
			print(f"Warning: Failed to load metadata file: {e}")
			return {}
	return {}


def save_upload_metadata(metadata: dict) -> None:
	"""Save upload metadata to disk."""
	try:
		with open(METADATA_FILE, "w") as f:
			json.dump(metadata, f, indent=2)
	except Exception as e:
		print(f"Warning: Failed to save metadata file: {e}")


def get_or_create_gif_uuid(gif_path: Path) -> tuple[str, dict]:
	"""
	Get or create a UUID for a GIF file.
	Returns (uuid_str, metadata_dict) where metadata includes stored upload info.
	"""
	metadata = load_upload_metadata()
	file_hash = compute_file_hash(gif_path)
	
	if file_hash in metadata:
		return metadata[file_hash]["uuid"], metadata[file_hash]
	
	# New GIF: create entry
	new_uuid = str(uuid.uuid4())
	metadata[file_hash] = {
		"uuid": new_uuid,
		"original_path": str(gif_path),
		"created_at": datetime.now().isoformat(),
		"frames": []
	}
	save_upload_metadata(metadata)
	return new_uuid, metadata[file_hash]


def record_uploaded_frame(gif_path: Path, frame_name: str) -> None:
	"""Record that a frame has been uploaded."""
	metadata = load_upload_metadata()
	file_hash = compute_file_hash(gif_path)
	if file_hash in metadata:
		if frame_name not in metadata[file_hash]["frames"]:
			metadata[file_hash]["frames"].append(frame_name)
		save_upload_metadata(metadata)


def is_gif_already_uploaded(gif_path: Path) -> bool:
	"""Check if a GIF has already been fully uploaded."""
	metadata = load_upload_metadata()
	file_hash = compute_file_hash(gif_path)
	if file_hash in metadata:
		return len(metadata[file_hash]["frames"]) > 0
	return False


def list_stored_gifs() -> dict:
	"""List all stored GIFs with their UUIDs."""
	metadata = load_upload_metadata()
	result = {}
	for file_hash, info in metadata.items():
		result[info["uuid"]] = {
			"original_path": info["original_path"],
			"frame_count": len(info["frames"]),
			"created_at": info["created_at"]
		}
	return result



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
		print(f"Processing {gif_path.name}...")
		
		# Check if this GIF has already been uploaded
		gif_uuid, gif_info = get_or_create_gif_uuid(gif_path)
		already_uploaded = is_gif_already_uploaded(gif_path)
		
		if already_uploaded:
			print(f"✓ GIF already uploaded (UUID: {gif_uuid})")
			print(f"  Using {len(gif_info['frames'])} cached frames")
			frames = gif_info["frames"]
			stored_durations = gif_info.get("durations", [1.0] * len(frames))
		else:
			print(f"→ Uploading new GIF (UUID: {gif_uuid})")
			
			max_frames_env = os.getenv("ASTRA_MAX_FRAMES")
			frame_step_env = os.getenv("ASTRA_FRAME_STEP")
			upload_timeout_env = os.getenv("ASTRA_UPLOAD_TIMEOUT")
			upload_retries_env = os.getenv("ASTRA_UPLOAD_RETRIES")
			format_storage_env = os.getenv("ASTRA_FORMAT_STORAGE")
			max_frames = int(max_frames_env) if max_frames_env else None
			frame_step = max(1, int(frame_step_env)) if frame_step_env else 1
			upload_timeout = float(upload_timeout_env) if upload_timeout_env else 25.0
			upload_retries = max(1, int(upload_retries_env)) if upload_retries_env else 3
			format_storage = True if format_storage_env is None else format_storage_env.lower() in ("1", "true", "yes", "on")
			
			if format_storage:
				print("Formatting ESP32 display storage...")
				display.format_storage()
			
			img = Image.open(gif_path)
			frames = []
			durations = []
			
			for i, frame in enumerate(ImageSequence.Iterator(img)):
				if i % frame_step != 0:
					continue
				if max_frames is not None and len(frames) >= max_frames:
					break
				duration = frame.info.get("duration", 100) / 1000.0
				durations.append(duration)
				raw = image_to_rgb565_bytes(frame, ESP32Display.WIDTH, ESP32Display.HEIGHT)
				name = f"{gif_path.stem}_{i}.rgb"
				print(f"  Uploading frame {i} as {name} ({len(raw)} bytes)...")
				last_exc = None
				for attempt in range(1, upload_retries + 1):
					try:
						conn.upload_display_file(name, raw, timeout=upload_timeout)
						last_exc = None
						record_uploaded_frame(gif_path, name)
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
			
			# Store durations in metadata
			metadata = load_upload_metadata()
			file_hash = compute_file_hash(gif_path)
			if file_hash in metadata:
				metadata[file_hash]["durations"] = durations
				save_upload_metadata(metadata)
			
			stored_durations = durations

		print("Upload complete. Playing from ESP32...")
		loops = 1
		for loop in range(loops):
			for idx, name in enumerate(frames):
				conn.play_display_file(name, x=0, y=0, w=ESP32Display.WIDTH, h=ESP32Display.HEIGHT)
				time.sleep(stored_durations[idx] if idx < len(stored_durations) else 1.0)
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



def list_stored_gifs_cmd() -> None:
	"""List all stored GIFs."""
	gifs = list_stored_gifs()
	if not gifs:
		print("No stored GIFs found.")
		return
	print("\nStored GIFs:")
	print("-" * 80)
	for uuid_str, info in gifs.items():
		print(f"UUID: {uuid_str}")
		print(f"  Path: {info['original_path']}")
		print(f"  Frames: {info['frame_count']}")
		print(f"  Created: {info['created_at']}")
		print()


def play_stored_gif_by_uuid(uuid_str: str) -> None:
	"""Play a stored GIF by UUID without re-uploading."""
	metadata = load_upload_metadata()
	gif_entry = None
	for file_hash, info in metadata.items():
		if info["uuid"] == uuid_str:
			gif_entry = info
			break
	
	if not gif_entry:
		print(f"GIF with UUID {uuid_str} not found.")
		return
	
	conn = None
	display = None
	try:
		print(f"Playing GIF: {gif_entry['original_path']} (UUID: {uuid_str})")
		conn = ESP32Connection()
		display = ESP32Display(conn)
		print("  Initializing display...")
		init_result = display.initialize()
		print(f"  Display initialized: {init_result}")
		
		# Ensure backlight is on
		display.set_backlight(255)
		display.power(True)
		time.sleep(0.2)
		
		# Test: clear display and show a test color to verify display is working
		print("  Testing display with solid color...")
		display.clear("FF0000")  # Red
		time.sleep(0.5)
		
		frames = gif_entry["frames"]
		durations = gif_entry.get("durations", [1.0] * len(frames))
		
		print(f"Playing {len(frames)} frames from ESP32...")
		for idx, name in enumerate(frames):
			result = conn.play_display_file(name, x=0, y=0, w=ESP32Display.WIDTH, h=ESP32Display.HEIGHT)
			if idx == 0:
				print(f"  First frame: {result}")
			time.sleep(durations[idx] if idx < len(durations) else 1.0)
			time.sleep(durations[idx] if idx < len(durations) else 1.0)
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

