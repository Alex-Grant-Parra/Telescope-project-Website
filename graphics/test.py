#!/usr/bin/env python3
"""Asset management utilities for ESP32."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from graphics.assets_player import (
	list_remote_assets,
	remote_storage_info,
	delete_remote_asset,
)


def clear_all_remote_assets() -> None:
	"""List all assets on the ESP32 and delete them one by one."""
	print("Fetching assets from ESP32...")
	try:
		files = list_remote_assets()
		if not files:
			print("No assets found on device.")
			return
		
		print(f"Found {len(files)} items on device:")
		for name in sorted(files.keys()):
			print(f"  {name}")
		
		print("\nDeleting all assets...")
		for name in sorted(files.keys()):
			try:
				delete_remote_asset(name)
				print(f"  ✓ Deleted {name}")
			except Exception as e:
				print(f"  ✗ Failed to delete {name}: {e}")
		
		# Show final storage info
		info = remote_storage_info()
		print(f"\nFinal storage: {info['used_bytes']} / {info['total_bytes']} bytes used")
	except Exception as e:
		print(f"Error: {e}")



if __name__ == "__main__":
	clear_all_remote_assets()
