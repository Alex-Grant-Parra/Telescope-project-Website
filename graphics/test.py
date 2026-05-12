#!/usr/bin/env python3
"""Example app-style entry point for asset sync and playback."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from graphics.assets_player import play_asset, sync_assets_folder


def main() -> None:
	"""Prepare all assets, then play a PNG and a GIF by filename."""
	assets_dir = ROOT / "graphics" / "assets"
	print("Syncing assets folder...")
	sync_assets_folder(assets_dir=assets_dir)

	print("Playing test.png...")
	play_asset("test.png", assets_dir=assets_dir, auto_sync=False)

	print("Playing test.gif...")
	for x in range(0, 5):
		play_asset("test.gif", assets_dir=assets_dir, auto_sync=False)


if __name__ == "__main__":
	main()