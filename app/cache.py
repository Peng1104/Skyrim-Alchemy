"""Shared on-disk cache directories, used by both the scraping and inventory domains."""
from pathlib import Path

CACHE_DIRECTORY = Path("cache")

# Scraped UESP HTML pages (Alchemy_Effects, Ingredients, per-effect priority pages).
PAGES_CACHE_DIRECTORY = CACHE_DIRECTORY / "pages"

# Inventory OCR snapshots (JSON) - kept separate from HTML so old snapshots can
# be copied aside and diffed later, without dragging along scraped wiki pages.
INVENTORY_CACHE_DIRECTORY = CACHE_DIRECTORY / "inventory"

# One JSON file per screenshot (its raw OCR result) - see app.inventory._inventory.
SCREENSHOTS_CACHE_DIRECTORY = CACHE_DIRECTORY / "screenshots"

PAGES_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
INVENTORY_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)


def clear_pages_cache() -> int:
    """
    Delete every cached UESP HTML page, forcing a fresh scrape on next use.

    Returns
    -------
    int
        Number of files deleted.
    """
    deleted = 0

    for file in PAGES_CACHE_DIRECTORY.glob("*.html"):
        file.unlink()
        deleted += 1

    return deleted
