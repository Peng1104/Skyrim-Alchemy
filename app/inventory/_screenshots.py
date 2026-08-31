"""Skyrim screenshot file discovery in the game directory."""
import re
from os import PathLike
from pathlib import Path

from PIL import Image

from app.i18n import translate


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


def find_screenshot_paths(game_path: PathLike[str] | str) -> dict[int, Path]:
    """
    Find screenshot file paths in the Skyrim game directory, keyed by screenshot ID.

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

    for image_path in game_path.glob("ScreenShot*.png"):
        img_id = extract_screenshot_id(image_path.name)

        if img_id < 0:
            continue

        paths[img_id] = image_path

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
