"""Asset upload and playback management.

This module scans `graphics/assets`, converts supported files to the display
resolution, uploads them to ESP32 flash, and plays them back by filename.
PNG/JPG/BMP/WebP files are stored as single RGB565 frames. GIFs are split into
frames and played back as an animation.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from esp32.interfaceESP32 import ESP32Connection, ESP32Display
from graphics.image_display import image_to_rgb565_bytes
from PIL import Image, ImageSequence


ASSETS_DIR = ROOT / "graphics" / "assets"
ASSET_INDEX_FILE = ROOT / ".astra_assets.json"
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}


def _asset_name(asset_path: Path) -> str:
	return asset_path.name


def _compute_file_hash(file_path: Path) -> str:
	sha256_hash = hashlib.sha256()
	with open(file_path, "rb") as file_handle:
		for byte_block in iter(lambda: file_handle.read(4096), b""):
			sha256_hash.update(byte_block)
	return sha256_hash.hexdigest()


def _load_index() -> dict[str, Any]:
	if not ASSET_INDEX_FILE.exists():
		return {}
	try:
		with open(ASSET_INDEX_FILE, "r") as file_handle:
			return json.load(file_handle)
	except Exception as exc:
		print(f"Warning: failed to load asset index: {exc}")
		return {}


def _save_index(index: dict[str, Any]) -> None:
	try:
		with open(ASSET_INDEX_FILE, "w") as file_handle:
			json.dump(index, file_handle, indent=2)
	except Exception as exc:
		print(f"Warning: failed to save asset index: {exc}")


def clear_asset_index() -> None:
	"""Remove the on-disk asset index."""
	if ASSET_INDEX_FILE.exists():
		ASSET_INDEX_FILE.unlink()


def list_assets() -> dict[str, Any]:
	"""Return the current asset index."""
	return _load_index()


def list_remote_assets(timeout: float = 5.0, conn: ESP32Connection | None = None) -> dict[str, int]:
	"""Query the ESP32 for stored files and return dict of {name: size}.

	Automatically groups GIF frame sequences (e.g., prefix_0000.rgb, prefix_0001.rgb)
	into synthetic entries (prefix.gif with combined size).
	Raises on connection errors.
	"""
	import re
	own_conn = False
	if conn is None:
		conn = ESP32Connection()
		own_conn = True
	display = ESP32Display(conn)
	try:
		display.initialize()
		resp = display.list_files()
		files = resp.get("files", [])
		
		# Build dict and group GIF frames
		file_dict: dict[str, int] = {}
		frame_prefixes: dict[str, list[tuple[str, int]]] = {}  # prefix -> [(name, size), ...]
		
		for f in files:
			name = f.get("name", "")
			# Normalize device-returned names which may include a leading '/'
			if name.startswith('/'):
				name = name[1:]
			size = f.get("size", 0)
			
			# Check if this is a numbered frame: matches pattern like "prefix_XXXX.rgb"
			match = re.match(r'^(.+?)_(\d{4})\.rgb$', name)
			if match:
				prefix = match.group(1)
				if prefix not in frame_prefixes:
					frame_prefixes[prefix] = []
				frame_prefixes[prefix].append((name, size))
			else:
				# Regular file, add directly
				file_dict[name] = size
		
		# Convert grouped frames into GIF entries
		for prefix, frames in frame_prefixes.items():
			if len(frames) > 1:
				# Multiple frames: treat as a GIF
				total_size = sum(size for _, size in frames)
				file_dict[f"{prefix}.gif"] = total_size
			else:
				# Single frame: keep as .rgb
				file_dict[frames[0][0]] = frames[0][1]
		
		if not file_dict:
			# Debug helper: show raw response structure when device reports no files
			try:
				print(f"[Assets] Remote list_files raw response: {resp!r}")
			except Exception:
				pass
		return file_dict
	finally:
		if own_conn:
			try:
				conn.close()
			except Exception:
				pass


def remote_storage_info(conn: ESP32Connection | None = None) -> dict[str, int]:
	"""Return storage info from ESP32: total_bytes, used_bytes, free_bytes."""
	own_conn = False
	if conn is None:
		conn = ESP32Connection()
		own_conn = True
	display = ESP32Display(conn)
	try:
		display.initialize()
		return display.storage_info()
	finally:
		if own_conn:
			try:
				conn.close()
			except Exception:
				pass


def delete_remote_asset(name: str, conn: ESP32Connection | None = None) -> None:
	"""Delete a stored file on the ESP32 by name.
	
	For synthetic GIF names (e.g., "test.gif"), deletes all frame files.
	For regular files, deletes the file directly.
	Raises on error.
	"""
	import re
	own_conn = False
	if conn is None:
		conn = ESP32Connection()
		own_conn = True
	display = ESP32Display(conn)
	try:
		display.initialize()
		
		# Check if this is a synthetic GIF name (ends with .gif)
		if name.endswith(".gif"):
			prefix = name[:-4]  # Remove .gif extension
			# Delete only the frame files that exist on the device right now.
			frame_pattern = re.compile(rf'^{re.escape(prefix)}_\d{{4}}\.rgb$')
			resp = display.list_files()
			files = resp.get("files", [])
			matching_files = []
			for f in files:
				fname = f.get("name", "")
				if fname.startswith('/'):
					fname = fname[1:]
				if frame_pattern.match(fname):
					matching_files.append(fname)
			
			if not matching_files:
				raise RuntimeError(f"No frame files found for GIF: {name}")
			
			# Delete each frame file
			for frame_file in matching_files:
				display.delete_file(frame_file)
				time.sleep(0.02)
		else:
			# Regular file - delete directly
			display.delete_file(name)
	finally:
		if own_conn:
			try:
				conn.close()
			except Exception:
				pass


def _asset_is_current(asset_path: Path, entry: dict[str, Any]) -> bool:
	return entry.get("source_hash") == _compute_file_hash(asset_path) and bool(entry.get("stored_files"))


def _upload_with_retries(
	conn: ESP32Connection,
	display: ESP32Display,
	stored_name: str,
	payload: bytes,
	upload_timeout: float,
	upload_retries: int,
) -> tuple[ESP32Connection, ESP32Display]:
	last_exc: Exception | None = None
	for attempt in range(1, upload_retries + 1):
		try:
			conn.upload_display_file(stored_name, payload, timeout=upload_timeout)
			return conn, display
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
	return conn, display


def _upload_image_asset(
	conn: ESP32Connection,
	display: ESP32Display,
	asset_path: Path,
	width: int,
	height: int,
	upload_timeout: float,
	upload_retries: int,
) -> dict[str, Any]:
	with Image.open(asset_path) as image:
		rgb565_data = image_to_rgb565_bytes(image, width, height)

	asset_hash = _compute_file_hash(asset_path)
	stored_name = f"{asset_path.stem}_{asset_hash[:8]}.rgb"
	conn, display = _upload_with_retries(conn, display, stored_name, rgb565_data, upload_timeout, upload_retries)
	return {
		"kind": "image",
		"source_hash": asset_hash,
		"source_path": str(asset_path),
		"stored_files": [stored_name],
		"width": width,
		"height": height,
		"created_at": datetime.now().isoformat(),
	}


def _upload_gif_asset(
	conn: ESP32Connection,
	display: ESP32Display,
	asset_path: Path,
	width: int,
	height: int,
	upload_timeout: float,
	upload_retries: int,
) -> dict[str, Any]:
	asset_hash = _compute_file_hash(asset_path)
	frame_files: list[str] = []
	durations: list[float] = []
	with Image.open(asset_path) as image:
		for frame_index, frame in enumerate(ImageSequence.Iterator(image)):
			duration = frame.info.get("duration", 100) / 1000.0
			durations.append(duration)
			rgb565_data = image_to_rgb565_bytes(frame, width, height)
			stored_name = f"{asset_path.stem}_{asset_hash[:8]}_{frame_index:04d}.rgb"
			conn, display = _upload_with_retries(conn, display, stored_name, rgb565_data, upload_timeout, upload_retries)
			frame_files.append(stored_name)

	return {
		"kind": "gif",
		"source_hash": asset_hash,
		"source_path": str(asset_path),
		"stored_files": frame_files,
		"durations": durations,
		"frame_count": len(frame_files),
		"width": width,
		"height": height,
		"created_at": datetime.now().isoformat(),
	}


def sync_assets_folder(
	assets_dir: Path | None = None,
	width: int = ESP32Display.WIDTH,
	height: int = ESP32Display.HEIGHT,
	upload_timeout: float = 25.0,
	upload_retries: int = 3,
	rebuild: bool = False,
	conn: ESP32Connection | None = None,
) -> dict[str, Any]:
	"""Upload all supported assets in the folder and cache them for quick access.
	
	Args:
		conn: Optional existing ESP32Connection. If not provided, creates a new one.
	"""
	assets_dir = assets_dir or ASSETS_DIR
	if not assets_dir.exists():
		raise FileNotFoundError(f"Assets folder not found: {assets_dir}")

	index = _load_index()
	results: dict[str, Any] = {}
	own_conn = False
	display = None

	try:
		# Use provided connection or create a new one
		if conn is None:
			print("Connecting to ESP32...")
			conn = ESP32Connection()
			own_conn = True
		
		display = ESP32Display(conn)
		display.initialize()

		# Fetch device file list once to validate cached entries (normalize leading '/')
		try:
			_device_files = display.list_files().get("files", [])
			_device_file_names = set()
			for f in _device_files:
				fname = f.get("name", "")
				if fname.startswith('/'):
					fname = fname[1:]
				_device_file_names.add(fname)
		except Exception:
			_device_file_names = set()

		if rebuild:
			print("Formatting ESP32 storage for a full rebuild...")
			display.format_storage()

		for asset_path in sorted(assets_dir.iterdir()):
			if not asset_path.is_file() or asset_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
				continue

			asset_key = _asset_name(asset_path)
			existing_entry = index.get(asset_key)
			# If we have an index entry, ensure it truly exists on device as well
			if existing_entry and not rebuild and _asset_is_current(asset_path, existing_entry):
				stored_ok = True
				for sf in existing_entry.get("stored_files", []):
					check_name = sf[1:] if sf.startswith('/') else sf
					if check_name not in _device_file_names:
						stored_ok = False
						break
				if stored_ok:
					print(f"✓ Cached: {asset_key}")
					results[asset_key] = existing_entry
					continue
				# Device missing files; fall through to upload

			print(f"Uploading {asset_key}...")
			if asset_path.suffix.lower() == ".gif":
				entry = _upload_gif_asset(conn, display, asset_path, width, height, upload_timeout, upload_retries)
			else:
				entry = _upload_image_asset(conn, display, asset_path, width, height, upload_timeout, upload_retries)

			entry["uuid"] = existing_entry.get("uuid") if existing_entry else str(uuid.uuid4())
			entry["asset_name"] = asset_key
			index[asset_key] = entry
			results[asset_key] = entry
			_save_index(index)

		print(f"Prepared {len(results)} asset(s).")
		return results
	finally:
		# Only close connection if we created it, don't close provided ones
		if own_conn and conn is not None:
			try:
				conn.close()
			except Exception:
				pass


def play_asset(
	asset_name: str,
	assets_dir: Path | None = None,
	auto_sync: bool = True,
	width: int = ESP32Display.WIDTH,
	height: int = ESP32Display.HEIGHT,
	upload_timeout: float = 25.0,
	upload_retries: int = 3,
	rebuild: bool = False,
	smooth: bool = False,
) -> None:
	"""Play an uploaded asset by filename, for example `test.png` or `test.gif`."""
	assets_dir = assets_dir or ASSETS_DIR
	asset_key = Path(asset_name).name
	index = _load_index()
	entry = index.get(asset_key)
	if entry is None and auto_sync:
		sync_assets_folder(
			assets_dir=assets_dir,
			width=width,
			height=height,
			upload_timeout=upload_timeout,
			upload_retries=upload_retries,
			rebuild=rebuild,
		)
		index = _load_index()
		entry = index.get(asset_key)

	if entry is None:
		raise FileNotFoundError(f"Asset not found in cache: {asset_key}")

	conn = None
	display = None
	try:
		print(f"Playing {asset_key}...")
		conn = ESP32Connection()
		display = ESP32Display(conn)
		display.initialize()
		display.set_backlight(255)
		display.power(True)
		time.sleep(0.2)

		if entry.get("kind") == "gif":
			# Smooth playback option: stream frames directly from the source GIF
			# to the display over the open connection rather than issuing a
			# separate `play_display_file` call per frame. This reduces
			# per-frame round-trip overhead and makes animation smoother.
			if smooth:
				# For robust smooth playback, instruct the ESP32 to play the
				# already-uploaded sequence of stored frame files. This avoids
				# streaming pixel data at playback time and yields smooth timing.
				stored_frames = entry.get("stored_files", [])
				durations_s = entry.get("durations", [])
				if not stored_frames:
					raise RuntimeError("No stored frames available for smooth playback")
				durations_ms = [int(d * 1000) for d in durations_s]
				# Derive prefix from the first stored filename: strip trailing
				# numeric index and extension, leaving the base prefix the
				# firmware expects (e.g. 'test_4d1bc68f_').
				first = stored_frames[0]
				# Find the last underscore before the numeric index
				stem = first
				# Remove extension
				if stem.endswith('.rgb'):
					stem = stem[:-4]
				# Trim trailing digits
				import re
				m = re.match(r"^(.*?_)(\d+)$", stem)
				if not m:
					# Fall back to explicit list if prefix cannot be derived
					print("  Could not derive prefix; falling back to explicit file list")
					conn.play_sequence(stored_frames, durations_ms, x=0, y=0, w=width, h=height)
				else:
					prefix = m.group(1)
					count = len(stored_frames)
					print(f"  Requesting device-side prefix playback: {prefix} ({count} frames)")
					# Calculate reasonable timeout: sum of frame durations + margin
					total_ms = sum(durations_ms) if durations_ms else count * 100
					timeout_s = max(5.0, total_ms / 1000.0 + 5.0)
					conn.play_sequence_prefix(prefix, count, start=0, pad=len(m.group(2)), durations_ms=durations_ms, x=0, y=0, w=width, h=height, timeout=timeout_s)
            
			else:
				frames = entry.get("stored_files", [])
				durations = entry.get("durations", [1.0] * len(frames))
				print(f"  GIF frames: {len(frames)}")
				for index, stored_name in enumerate(frames):
					conn.play_display_file(stored_name, x=0, y=0, w=width, h=height)
					time.sleep(durations[index] if index < len(durations) else 1.0)
		else:
			stored_files = entry.get("stored_files", [])
			if not stored_files:
				raise RuntimeError(f"No stored file recorded for asset: {asset_key}")
			conn.play_display_file(stored_files[0], x=0, y=0, w=width, h=height)

		print("Done.")
	finally:
		if conn is not None:
			try:
				conn.close()
			except Exception:
				pass


def sync_assets_on_connect(conn: ESP32Connection | None = None) -> bool:
	"""Sync assets from RPi to ESP32 on startup.
	
	Flashes blue LED during sync and uploads all assets.
	
	Args:
		conn: Optional existing ESP32Connection instance. If not provided,
			  will attempt to create a new connection.
	
	Returns:
		True if sync completed successfully, False otherwise
	"""
	def _sync_with_led(existing_conn: ESP32Connection | None) -> None:
		conn_to_use = existing_conn
		own_conn = False
		led = None
		try:
			# Only create a new connection if one wasn't provided
			if conn_to_use is None:
				print("[Assets] Connecting to ESP32 for asset sync...")
				conn_to_use = ESP32Connection()
				own_conn = True
			
			# Import here to avoid circular dependency
			from esp32.interfaceESP32 import ESP32LED
			
			# Try to flash blue LED during sync
			try:
				led = ESP32LED(conn_to_use)
				led.blue.blink(interval_ms=500)
				print("[Assets] Blue LED blinking during asset sync")
			except Exception as e:
				print(f"[Assets] Could not control LED: {e}")
				led = None
			
			try:
				print("[Assets] Starting asset sync to ESP32...")
				sync_assets_folder(conn=conn_to_use)
				print("[Assets] Asset sync completed successfully")
			finally:
				# Stop the LED blinking
				if led is not None:
					try:
						time.sleep(0.5)
						led.blue.off()
						print("[Assets] Blue LED turned off")
						time.sleep(0.5)
					except Exception:
						pass
		except Exception as e:
			print(f"[Assets] Error during asset sync: {e}")
			# Try to turn off LED in case of error
			if led is not None:
				try:
					led.blue.off()
				except Exception:
					pass
		finally:
			# Only close the connection if we created it
			if own_conn and conn_to_use is not None:
				try:
					conn_to_use.close()
				except Exception:
					pass
	
	try:
		_sync_with_led(conn)
		return True
	except Exception as e:
		print(f"[Assets] Failed to start asset sync thread: {e}")
		return False


prepare_assets_folder = sync_assets_folder
