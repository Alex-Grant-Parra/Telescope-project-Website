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
) -> dict[str, Any]:
	"""Upload all supported assets in the folder and cache them for quick access."""
	assets_dir = assets_dir or ASSETS_DIR
	if not assets_dir.exists():
		raise FileNotFoundError(f"Assets folder not found: {assets_dir}")

	index = _load_index()
	results: dict[str, Any] = {}
	conn = None
	display = None

	try:
		print("Connecting to ESP32...")
		conn = ESP32Connection()
		display = ESP32Display(conn)
		display.initialize()

		if rebuild:
			print("Formatting ESP32 storage for a full rebuild...")
			display.format_storage()

		for asset_path in sorted(assets_dir.iterdir()):
			if not asset_path.is_file() or asset_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
				continue

			asset_key = _asset_name(asset_path)
			existing_entry = index.get(asset_key)
			if existing_entry and not rebuild and _asset_is_current(asset_path, existing_entry):
				print(f"✓ Cached: {asset_key}")
				results[asset_key] = existing_entry
				continue

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
		if conn is not None:
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


prepare_assets_folder = sync_assets_folder
