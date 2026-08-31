"""Steam client discovery: finds the Skyrim Special Edition install path automatically."""
import platform
import re
from pathlib import Path


def _steam_root() -> Path | None:
    """
    Get the best-effort path to the Steam client installation for the current OS.

    Returns
    -------
    Path | None
        The first existing Steam client directory, or None if not found.
    """
    system = platform.system()

    if system == "Windows":
        candidates = [
            Path("C:/Program Files (x86)/Steam"),
            Path("C:/Program Files/Steam"),
        ]
    elif system == "Darwin":
        candidates = [Path.home() / "Library/Application Support/Steam"]
    else:  # Linux
        candidates = [
            Path.home() / ".steam/steam",
            Path.home() / ".local/share/Steam",
        ]

    return next((candidate for candidate in candidates if candidate.exists()), None)


def _steam_library_paths(steam_root: Path) -> list[Path]:
    """
    Parse steamapps/libraryfolders.vdf for every registered Steam library folder.

    Includes additional libraries registered on other disks.

    Parameters
    ----------
    steam_root : Path
        Path to the Steam client installation.

    Returns
    -------
    list[Path]
        Registered library folder paths, or [steam_root] if none found.
    """
    vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"

    if not vdf_path.exists():
        return [steam_root]

    content = vdf_path.read_text(encoding="utf-8", errors="ignore")
    paths = [Path(p) for p in re.findall(r'"path"\s+"([^"]+)"', content)]

    return paths or [steam_root]


def default_game_directory() -> str:
    """
    Get the best-effort Skyrim Special Edition install path.

    Finds the Steam client for the current OS, reads every registered library
    folder (including ones on other disks) from libraryfolders.vdf, and returns
    the first one containing "Skyrim Special Edition". Falls back to a single
    OS-typical guess if Steam or the game can't be located.

    Returns
    -------
    str
        Path to the Skyrim Special Edition installation.
    """
    steam_root = _steam_root()

    if steam_root is not None:
        for library in _steam_library_paths(steam_root):
            candidate = library / "steamapps" / "common" / "Skyrim Special Edition"
            if candidate.exists():
                return str(candidate)

    system = platform.system()

    if system == "Windows":
        return "C:/Program Files (x86)/Steam/steamapps/common/Skyrim Special Edition"
    if system == "Darwin":
        return str(
            Path.home()
            / "Library/Application Support/Steam/steamapps/common/Skyrim Special Edition"
        )

    return str(Path.home() / ".local/share/Steam/steamapps/common/Skyrim Special Edition")
