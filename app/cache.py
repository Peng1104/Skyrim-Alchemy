"""Shared on-disk cache directories, used by the inventory and game-data domains."""
from pathlib import Path

CACHE_DIRECTORY = Path("cache")

# Inventory OCR snapshots (JSON) - kept separate so old snapshots can be
# copied aside and diffed later, without dragging along the game-data cache.
INVENTORY_CACHE_DIRECTORY = CACHE_DIRECTORY / "inventory"

# One JSON file per screenshot (its raw OCR result) - see app.inventory._inventory.
SCREENSHOTS_CACHE_DIRECTORY = CACHE_DIRECTORY / "screenshots"

# The full ingredient/effect database, read from every active plugin's
# binary data, plus the scan manifest - see app.game_data._scan.
GAME_DATA_CACHE_DIRECTORY = CACHE_DIRECTORY / "game_data"

INVENTORY_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
GAME_DATA_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
