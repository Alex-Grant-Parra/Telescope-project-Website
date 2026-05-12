"""GIF storage and caching management.

Handles persistent storage of uploaded GIFs with UUID tracking,
metadata persistence, and cache queries.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime
import uuid


def _get_metadata_file() -> Path:
	"""Get path to metadata file in project root."""
	root = Path(__file__).resolve().parent.parent
	return root / ".astra_uploads.json"


def compute_file_hash(file_path: Path) -> str:
	"""Compute SHA256 hash of a file."""
	sha256_hash = hashlib.sha256()
	with open(file_path, "rb") as f:
		for byte_block in iter(lambda: f.read(4096), b""):
			sha256_hash.update(byte_block)
	return sha256_hash.hexdigest()


def load_metadata() -> dict:
	"""Load upload metadata from disk."""
	metadata_file = _get_metadata_file()
	if metadata_file.exists():
		try:
			with open(metadata_file, "r") as f:
				return json.load(f)
		except Exception as e:
			print(f"Warning: Failed to load metadata file: {e}")
			return {}
	return {}


def save_metadata(metadata: dict) -> None:
	"""Save upload metadata to disk."""
	metadata_file = _get_metadata_file()
	try:
		with open(metadata_file, "w") as f:
			json.dump(metadata, f, indent=2)
	except Exception as e:
		print(f"Warning: Failed to save metadata file: {e}")


def get_or_create_gif_uuid(gif_path: Path) -> tuple[str, dict]:
	"""
	Get or create a UUID for a GIF file.
	Returns (uuid_str, metadata_dict) where metadata includes stored upload info.
	"""
	metadata = load_metadata()
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
	save_metadata(metadata)
	return new_uuid, metadata[file_hash]


def record_uploaded_frame(gif_path: Path, frame_name: str) -> None:
	"""Record that a frame has been uploaded."""
	metadata = load_metadata()
	file_hash = compute_file_hash(gif_path)
	if file_hash in metadata:
		if frame_name not in metadata[file_hash]["frames"]:
			metadata[file_hash]["frames"].append(frame_name)
		save_metadata(metadata)


def record_frame_durations(gif_path: Path, durations: list[float]) -> None:
	"""Record frame durations for a GIF."""
	metadata = load_metadata()
	file_hash = compute_file_hash(gif_path)
	if file_hash in metadata:
		metadata[file_hash]["durations"] = durations
		save_metadata(metadata)


def is_gif_cached(gif_path: Path) -> bool:
	"""Check if a GIF has already been cached (uploaded)."""
	metadata = load_metadata()
	file_hash = compute_file_hash(gif_path)
	if file_hash in metadata:
		return len(metadata[file_hash]["frames"]) > 0
	return False


def get_cached_gif_info(gif_path: Path) -> dict | None:
	"""Get cached GIF info if it exists."""
	metadata = load_metadata()
	file_hash = compute_file_hash(gif_path)
	return metadata.get(file_hash)


def list_all_gifs() -> dict:
	"""List all stored GIFs with their UUIDs and metadata."""
	metadata = load_metadata()
	result = {}
	for file_hash, info in metadata.items():
		result[info["uuid"]] = {
			"original_path": info["original_path"],
			"frame_count": len(info["frames"]),
			"created_at": info["created_at"]
		}
	return result


def get_gif_by_uuid(uuid_str: str) -> dict | None:
	"""Get GIF metadata by UUID."""
	metadata = load_metadata()
	for file_hash, info in metadata.items():
		if info["uuid"] == uuid_str:
			return info
	return None


def clear_all_metadata() -> None:
	"""Clear all upload metadata."""
	metadata_file = _get_metadata_file()
	if metadata_file.exists():
		metadata_file.unlink()
