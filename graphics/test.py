#!/usr/bin/env python3
"""Example app-style entry point for asset sync and playback."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from graphics.assets_player import play_asset, sync_assets_folder
from graphics.image_display import clear_display
from time import sleep

from graphics.assets_player import (
	list_assets,
	list_remote_assets,
	remote_storage_info,
	delete_remote_asset,
)

def main() -> None:
	"""Prepare all assets, then play a PNG and a GIF by filename."""
	assets_dir = ROOT / "graphics" / "assets"
	print("Syncing assets folder...")
	sync_assets_folder(assets_dir=assets_dir)

	play_asset("test.png", assets_dir=assets_dir, auto_sync=False)
	sleep(2)
	play_asset("test.gif", assets_dir=assets_dir, auto_sync=False, smooth=True)
	play_asset("photoMe.jpg", assets_dir=assets_dir, auto_sync=False)
	sleep(5)
	clear_display()


def test_storage_helpers() -> None:
	"""Minimal test for the new storage helper functions.

	This attempts to exercise the local index function and will try to
	query the ESP32 for remote storage info if a device is available.
	Failures to contact a device are caught and reported as skipped.
	"""
	print("Running storage helper tests...")
	# Local index should always be loadable
	idx = list_assets()
	print(f"Local index contains {len(idx.get('assets', []))} assets")

	# Remote calls are optional and may fail when no device is connected
	try:
		files = list_remote_assets()
		print(f"Remote device reports {len(files)} files")
	except Exception as e:
		print(f"list_remote_assets() skipped: {e}")

	try:
		info = remote_storage_info()
		print(f"Remote storage: {info}")
	except Exception as e:
		print(f"remote_storage_info() skipped: {e}")

	print("Storage helper tests complete.")



if __name__ == "__main__":
	test_storage_helpers()