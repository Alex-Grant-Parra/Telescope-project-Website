#!/usr/bin/env python3
"""
GIF Manager - Utility to list and manage stored GIFs on ESP32.

Usage:
    python graphics/gif_manager.py list              # List all stored GIFs
    python graphics/gif_manager.py play <UUID>       # Play a GIF by UUID
    python graphics/gif_manager.py clear             # Clear all upload metadata
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from graphics import gif_storage
from graphics.gif_player import play_stored_gif_by_uuid


def cmd_list() -> None:
	"""List all stored GIFs."""
	gifs = gif_storage.list_all_gifs()
	if not gifs:
		print("No stored GIFs found.")
		return
	
	print("\n" + "=" * 80)
	print("Stored GIFs on ESP32".center(80))
	print("=" * 80)
	
	for idx, (uuid_str, info) in enumerate(gifs.items(), 1):
		print(f"\n{idx}. UUID: {uuid_str}")
		print(f"   Path: {info['original_path']}")
		print(f"   Frames: {info['frame_count']}")
		print(f"   Created: {info['created_at']}")
	
	print("\n" + "=" * 80)
	print(f"\nTotal: {len(gifs)} GIF(s) stored")


def cmd_play(uuid_str: str) -> None:
	"""Play a stored GIF by UUID."""
	play_stored_gif_by_uuid(uuid_str)


def cmd_clear() -> None:
	"""Clear all upload metadata."""
	metadata_file = Path(__file__).resolve().parent.parent / ".astra_uploads.json"
	if metadata_file.exists():
		confirm = input(
			f"⚠️  This will clear all stored GIF metadata from {metadata_file}.\n"
			"Continue? (yes/no): "
		)
		if confirm.lower() in ("yes", "y"):
			gif_storage.clear_all_metadata()
			print("✓ Metadata cleared.")
		else:
			print("Cancelled.")
	else:
		print("No metadata file found.")


def main() -> None:
	if len(sys.argv) < 2:
		print(__doc__)
		return
	
	command = sys.argv[1].lower()
	
	if command == "list":
		cmd_list()
	elif command == "play":
		if len(sys.argv) < 3:
			print("Error: UUID required for 'play' command")
			print("Usage: python graphics/gif_manager.py play <UUID>")
			sys.exit(1)
		cmd_play(sys.argv[2])
	elif command == "clear":
		cmd_clear()
	else:
		print(f"Unknown command: {command}")
		print(__doc__)
		sys.exit(1)


if __name__ == "__main__":
	main()
