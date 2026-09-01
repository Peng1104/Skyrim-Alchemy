"""Inventory retrieval: orchestrates screenshot discovery, OCR, and on-disk caching."""
import json
from pathlib import Path
from typing import Iterable

from PIL import Image

from app.cache import INVENTORY_CACHE_DIRECTORY, SCREENSHOTS_CACHE_DIRECTORY
from app.i18n import translate
from app.inventory._ocr import extract_ingredients_from_image
from app.inventory._screenshots import find_screenshot_paths
from app.models import InventoryIngredient, InventoryMarker, ScreenshotDetail, ScreenshotStatus

_MARKER_FILE = INVENTORY_CACHE_DIRECTORY / "marker.json"


class Inventory:
    """
    Class representing the Skyrim inventory, which contains ingredients.

    Retrieves the inventory data from the game directory by running OCR over
    the game's own screenshots. Each screenshot's OCR result is cached in its
    own JSON file (`cache/inventory/screenshots/<id>.json`), so combining an
    arbitrary range of screenshots later never requires re-running OCR, and
    old snapshots can be diffed even after the original screenshots are gone.
    """

    __game_directory: str
    ingredients: list[InventoryIngredient]

    def __init__(self, game_directory: str):
        """
        Initialize the Inventory with the game directory.

        Parameters
        ----------
        game_directory : str
            Path to the Skyrim game directory.
        """
        self.__game_directory = game_directory
        self.ingredients = []

    def _screenshot_cache_file(self, screenshot_id: int) -> Path:
        """
        Get the cache file path for a single screenshot's OCR result.

        Parameters
        ----------
        screenshot_id : int
            The screenshot's ID.

        Returns
        -------
        Path
            Path to that screenshot's cache file.
        """
        return SCREENSHOTS_CACHE_DIRECTORY / f"{screenshot_id}.json"

    def _cached_screenshot_ids(self) -> list[int]:
        """
        List every screenshot ID that has a cached OCR result on disk.

        Used to size the default combination range even when the original
        screenshots have since been deleted (e.g. via `delete_processed_screenshots`).

        Returns
        -------
        list[int]
            Cached screenshot IDs.
        """
        ids: list[int] = []

        for cache_file in SCREENSHOTS_CACHE_DIRECTORY.glob("*.json"):
            try:
                ids.append(int(cache_file.stem))
            except ValueError:
                continue

        return ids

    def _load_screenshot_cache(self, screenshot_id: int) -> list[InventoryIngredient] | None:
        """
        Load a single screenshot's cached OCR result, if present.

        Parameters
        ----------
        screenshot_id : int
            The screenshot's ID.

        Returns
        -------
        list[InventoryIngredient] | None
            The cached ingredients, or None if this screenshot has no cache yet.
        """
        cache_file = self._screenshot_cache_file(screenshot_id)

        if not cache_file.exists():
            return None

        with open(cache_file, "r") as f:
            return [InventoryIngredient.model_validate(ing) for ing in json.load(f)]

    def _save_screenshot_cache(
        self, screenshot_id: int, ingredients: list[InventoryIngredient]
    ) -> None:
        """
        Persist a single screenshot's OCR result to its own cache file.

        Parameters
        ----------
        screenshot_id : int
            The screenshot's ID.
        ingredients : list[InventoryIngredient]
            Ingredients recognized in that screenshot.
        """
        cache_file = self._screenshot_cache_file(screenshot_id)

        with open(cache_file, "w") as f:
            json.dump([ing.model_dump() for ing in ingredients], f, indent=2)

    def _save_marker(self, screenshot_ids: list[int]) -> None:
        """
        Persist the last combined screenshot ID list to disk.

        Parameters
        ----------
        screenshot_ids : list[int]
            Every screenshot ID included in the combination just produced.
        """
        marker = InventoryMarker(processed_screenshot_ids=screenshot_ids)

        with open(_MARKER_FILE, "w") as f:
            f.write(marker.model_dump_json(indent=2))

    def _available_screenshot_ids(self) -> list[int]:
        """
        List every screenshot ID that's either present on disk or already cached.

        Returns
        -------
        list[int]
            Every screenshot ID this Inventory could possibly combine right now.
        """
        all_paths = find_screenshot_paths(self.__game_directory)

        return sorted(set(all_paths) | set(self._cached_screenshot_ids()))

    def _load_marker(self) -> InventoryMarker | None:
        """
        Read the on-disk marker, if one has been saved yet.

        Returns
        -------
        InventoryMarker | None
            The marker, or None if no `retrieve` call has ever saved one.
        """
        if not _MARKER_FILE.exists():
            return None

        with open(_MARKER_FILE, "r") as f:
            return InventoryMarker.model_validate_json(f.read())

    def marker_screenshot_ids(self) -> list[int]:
        """
        Get the screenshot IDs recorded by the most recent `retrieve` call.

        Returns
        -------
        list[int]
            The marker's screenshot IDs, or an empty list if no marker exists yet.
        """
        marker = self._load_marker()

        return marker.processed_screenshot_ids if marker is not None else []

    def resolve_new_range(self) -> tuple[int, int] | None:
        """
        Resolve the (min_id, max_id) range for a default (no explicit --min/--max) run.

        Reads the marker left by the most recent `retrieve` call and compares it
        against what's actually available now (on disk or cached):

        - No marker yet (first ever run): combine everything from 0 to the
          highest available ID.
        - Screenshots newer than the marker's highest ID exist: combine only
          that delta (marker's highest ID + 1 up to the new highest ID). This
          becomes the new marker range, replacing the old one rather than
          accumulating with it - so an older, separately-captured session
          (e.g. this morning's screenshots) never gets silently merged back
          into today's inventory just because a later run also covers it.
        - Nothing new since the marker: replay the exact same range the
          marker recorded, so a plain re-run without new screenshots
          reproduces the last known inventory from cache instead of
          combining nothing.

        Returns
        -------
        tuple[int, int] | None
            The (min_id, max_id) to pass to `retrieve`, or None if there are
            no screenshots and no cache at all yet.
        """
        available_ids = self._available_screenshot_ids()
        marker_ids = self.marker_screenshot_ids()

        if not marker_ids:
            return (0, max(available_ids)) if available_ids else None

        last_min = min(marker_ids)
        last_max = max(marker_ids)
        available_max = max(available_ids, default=last_max)

        if available_max > last_max:
            return (last_max + 1, available_max)

        return (last_min, last_max)

    def list_screenshots(self) -> list[ScreenshotStatus]:
        """
        List every known screenshot ID with its on-disk availability.

        Covers both screenshots still present in the game directory and ones
        that only survive as a per-screenshot OCR cache (e.g. after
        `delete_processed_screenshots`), so nothing is silently left out.

        Returns
        -------
        list[ScreenshotStatus]
            One entry per screenshot ID, sorted ascending.
        """
        all_paths = find_screenshot_paths(self.__game_directory)
        cached_ids = set(self._cached_screenshot_ids())

        return [
            ScreenshotStatus(
                id=screenshot_id,
                has_image=screenshot_id in all_paths,
                has_cache=screenshot_id in cached_ids,
            )
            for screenshot_id in sorted(set(all_paths) | cached_ids)
        ]

    def screenshot_info(self, screenshot_id: int) -> ScreenshotDetail:
        """
        Get one screenshot's availability plus its cached OCR ingredients.

        Parameters
        ----------
        screenshot_id : int
            The screenshot's ID.

        Returns
        -------
        ScreenshotDetail
            The screenshot's status and cached ingredients (empty list if it
            has no cache yet).
        """
        all_paths = find_screenshot_paths(self.__game_directory)
        ingredients = self._load_screenshot_cache(screenshot_id)

        return ScreenshotDetail(
            id=screenshot_id,
            has_image=screenshot_id in all_paths,
            has_cache=ingredients is not None,
            ingredients=sorted(ingredients, key=lambda ing: ing.name) if ingredients else [],
        )

    def retrieve(
        self,
        known_names: Iterable[str],
        *,
        min_id: int | None = None,
        max_id: int | None = None,
        refresh: bool = False,
    ) -> None:
        """
        Retrieve the inventory by combining per-screenshot OCR results over a range.

        Screenshots already cached (from a previous run) are read straight from
        disk; only screenshots without a cache yet are actually OCR'd. This
        means the default (whole-history) range costs nothing extra for
        already-seen screenshots - only genuinely new ones get processed.

        Parameters
        ----------
        known_names : Iterable[str]
            Whitelist of valid ingredient names used to fuzzy-match OCR text
            and correct recognition errors.
        min_id : int | None, optional
            Lowest screenshot ID to include. Defaults to 0 (the whole history)
            when not given.
        max_id : int | None, optional
            Highest screenshot ID to include. Defaults to the newest screenshot
            found when not given.
        refresh : bool, optional
            If True, ignore any existing per-screenshot cache within the
            resolved range and re-run OCR for all of them, by default False.
        """
        all_paths = find_screenshot_paths(self.__game_directory)
        cached_ids = self._cached_screenshot_ids()

        if not all_paths and not cached_ids:
            print(translate("no_screenshots_found"))
            self.ingredients = []
            return

        known_names_list = list(known_names)
        lo = min_id if min_id is not None else 0
        hi = max_id if max_id is not None else max(*all_paths, *cached_ids)

        combined: dict[str, InventoryIngredient] = {}
        included_ids: list[int] = []
        newly_processed = 0

        for screenshot_id in range(lo, hi + 1):
            image_path = all_paths.get(screenshot_id)
            # `refresh` only forces re-OCR when the source image still exists -
            # if it was deleted (e.g. via --delete-old), fall back to the cache
            # instead of silently dropping that screenshot's ingredients.
            cached = None if (refresh and image_path is not None) \
                else self._load_screenshot_cache(screenshot_id)

            if cached is None:
                if image_path is None:
                    continue  # no screenshot with this ID and no cache - nothing to combine

                print(translate("reading_screenshot", id=screenshot_id))

                try:
                    img = Image.open(image_path)
                except Exception as img_error:
                    print(translate(
                        "error_loading_image", filename=image_path.name, error=img_error
                    ))
                    continue

                cached = extract_ingredients_from_image(img, known_names_list)
                self._save_screenshot_cache(screenshot_id, cached)
                newly_processed += 1

                print(translate("screenshot_processed", id=screenshot_id))

            included_ids.append(screenshot_id)

            for ingredient in cached:
                combined[ingredient.name] = ingredient

        self.ingredients = sorted(combined.values(), key=lambda ing: ing.name)

        if included_ids:
            self._save_marker(included_ids)

        if included_ids:
            print(translate(
                "ingredients_combined_range",
                count=len(self.ingredients),
                min_id=min(included_ids),
                max_id=max(included_ids),
                new_count=newly_processed,
            ))
        else:
            print(translate("ingredients_combined_empty"))

    def delete_processed_screenshots(self, ids: Iterable[int] | None = None) -> list[Path]:
        """
        Delete on-disk screenshots that already have a cached OCR result.

        Parameters
        ----------
        ids : Iterable[int] | None, optional
            Restrict deletion to these screenshot IDs. Screenshots outside
            this set are left untouched even if they're already cached.
            Defaults to every screenshot with a cache.

        Returns
        -------
        list[Path]
            Paths of the screenshots that were deleted.
        """
        wanted = set(ids) if ids is not None else None
        all_paths = find_screenshot_paths(self.__game_directory)
        to_delete = [
            path for screenshot_id, path in all_paths.items()
            if self._screenshot_cache_file(screenshot_id).exists()
            and (wanted is None or screenshot_id in wanted)
        ]

        for path in to_delete:
            path.unlink()

        return to_delete

    def delete_cached_screenshots(self, ids: Iterable[int] | None = None) -> list[int]:
        """
        Delete per-screenshot OCR cache files (not the screenshot images).

        Parameters
        ----------
        ids : Iterable[int] | None, optional
            Restrict deletion to these screenshot IDs. IDs outside this set
            are left untouched even if they're cached. Defaults to every
            cached screenshot ID.

        Returns
        -------
        list[int]
            Screenshot IDs whose cache was deleted.
        """
        wanted = set(ids) if ids is not None else None
        to_delete = [
            screenshot_id for screenshot_id in self._cached_screenshot_ids()
            if wanted is None or screenshot_id in wanted
        ]

        for screenshot_id in to_delete:
            self._screenshot_cache_file(screenshot_id).unlink()

        return sorted(to_delete)
