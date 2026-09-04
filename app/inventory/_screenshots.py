"""Skyrim screenshot file discovery in the game directory."""
import re
from os import PathLike
from pathlib import Path

from PIL import Image

from app.i18n import translate
from app.steam import skyrim_compatdata_dirs, steam_library_paths, steam_root


def _mo2_overwrite_screenshot_dirs() -> list[Path]:
    """
    Every plausible Mod Organizer 2 `overwrite/Root` screenshot directory.

    Mod Organizer 2 virtualizes the game's filesystem: a screenshot Skyrim
    writes to what it thinks is its own install directory is actually
    redirected to this profile-independent `overwrite` folder instead -
    confirmed empirically (a screenshot taken mid-session showed up only
    here, never in the real game install directory `find_screenshot_paths`'s
    caller otherwise scans). Globs every MO2 instance (not just one) under
    every Steam library's Proton compatdata prefix for Skyrim SE, mirroring
    `app.game_data._load_order._mo2_plugins_txt_candidates`.

    Returns
    -------
    list[Path]
        Candidate directories, newest compatdata first - existence is not
        checked here, callers filter that.
    """
    root = steam_root()

    if root is None:
        return []

    candidates: list[Path] = []

    for library in steam_library_paths(root):
        for compat_dir in skyrim_compatdata_dirs(library):
            mo2_base = (
                compat_dir / "pfx" / "drive_c" / "users" / "steamuser" / "AppData"
                / "Local" / "ModOrganizer"
            )
            candidates.extend(mo2_base.glob("*/overwrite/Root"))

    return candidates


def extract_screenshot_id(filename: str) -> int:
    """
    Extract the screenshot number from the filename.

    Parameters
    ----------
    filename : str
        Name of the screenshot file.

    Returns
    -------
    int
        Extracted screenshot number, or -1 if not found.
    """
    match = re.search(r'(\d+)', filename)

    return int(match.group(1)) if match else -1


def _scan_screenshot_dir(directory: Path, paths: dict[int, Path]) -> None:
    """
    Add every `ScreenShot*.png` in one directory into `paths`, keyed by ID.

    A later call (later directory scanned) overwrites an earlier one for the
    same ID - callers scan the MO2 `overwrite` directory (the live location
    under MO2's virtual filesystem) after the real game directory, so its
    entries win when a screenshot exists in both.

    Parameters
    ----------
    directory : Path
        Directory to scan (already checked to exist by the caller).
    paths : dict[int, Path]
        Accumulator mutated in place.
    """
    for image_path in directory.glob("ScreenShot*.png"):
        img_id = extract_screenshot_id(image_path.name)

        if img_id >= 0:
            paths[img_id] = image_path


def find_screenshot_paths(game_path: PathLike[str] | str) -> dict[int, Path]:
    """
    Find screenshot file paths for the current Skyrim install, keyed by screenshot ID.

    Scans both the real game directory and, if running under Mod Organizer 2,
    its `overwrite/Root` directory - MO2 virtualizes the game's filesystem,
    so a screenshot taken while playing is not necessarily written to the
    real game directory at all (see `_mo2_overwrite_screenshot_dirs`).

    Parameters
    ----------
    game_path : PathLike[str] | str
        Path to the Skyrim game directory.

    Returns
    -------
    dict[int, Path]
        Ordered dictionary mapping screenshot ID to file path.
    """
    if isinstance(game_path, str):
        game_path = Path(game_path)
    elif not isinstance(game_path, Path):
        raise ValueError("Game path must be a string or a Path object")

    paths: dict[int, Path] = {}

    if not game_path.exists():
        print(translate("game_directory_not_found", path=game_path))
        return paths

    _scan_screenshot_dir(game_path, paths)

    for mo2_dir in _mo2_overwrite_screenshot_dirs():
        if mo2_dir.exists():
            _scan_screenshot_dir(mo2_dir, paths)

    return dict(sorted(paths.items()))


def find_screenshot_images(game_path: PathLike[str] | str) -> dict[int, Image.Image]:
    """
    Find screenshot images in the skyrim game directory.

    Parameters
    ----------
    game_path : PathLike[str] | str
        Path to the Skyrim game directory.

    Returns
    -------
    dict[int, Image.Image]
        Ordered dictionary of screenshot images with screenshot ID as key
        and PIL Image object as value.
    """
    images: dict[int, Image.Image] = {}

    for img_id, image_path in find_screenshot_paths(game_path).items():
        try:
            images[img_id] = Image.open(image_path)

        except Exception as img_error:
            print(translate("error_loading_image", filename=image_path.name, error=img_error))
            continue

    return images
