"""
Active-plugin discovery: finds and parses the Skyrim `Plugins.txt` in use.

Tries a Mod Organizer 2 profile's `plugins.txt` under the Proton compatdata
prefix first (the common case for a modded Linux/Steam Deck install), then
the native (non-MO2) `Plugins.txt` location, per-OS.
"""
import os
import platform
from pathlib import Path

from app.steam import skyrim_compatdata_dirs, steam_library_paths, steam_root


def _mo2_plugins_txt_candidates() -> list[Path]:
    """
    Every plausible Mod Organizer 2 `plugins.txt` path, newest compatdata first.

    Globs every MO2 profile (not just "Default") under every Steam library's
    Proton compatdata prefix for Skyrim SE, since the profile name is
    user/instance-specific.

    Returns
    -------
    list[Path]
        Candidate paths, ordered by their compatdata directory's mtime
        (newest first) - existence is not checked here, callers filter that.
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
            candidates.extend(mo2_base.glob("*/profiles/*/plugins.txt"))

    return candidates


def _native_plugins_txt_candidates() -> list[Path]:
    """
    Every plausible native (non-MO2) `Plugins.txt` path for the current OS.

    Returns
    -------
    list[Path]
        Candidate paths - existence is not checked here, callers filter that.
    """
    system = platform.system()

    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")

        if not local_app_data:
            return []

        return [Path(local_app_data) / "Skyrim Special Edition" / "Plugins.txt"]

    root = steam_root()

    if root is None:
        return []

    candidates: list[Path] = []

    for library in steam_library_paths(root):
        for compat_dir in skyrim_compatdata_dirs(library):
            candidates.append(
                compat_dir / "pfx" / "drive_c" / "users" / "steamuser" / "AppData"
                / "Local" / "Skyrim Special Edition" / "Plugins.txt"
            )

    return candidates


def resolve_plugins_txt(override: str | None = None) -> Path | None:
    """
    Resolve the active `Plugins.txt` to read the mod load order from.

    Parameters
    ----------
    override : str | None, optional
        Explicit path from `Settings.plugins_txt_path`. Used as-is if it
        exists, bypassing auto-detection entirely.

    Returns
    -------
    Path | None
        The resolved `Plugins.txt` path, or None if nothing could be found
        (auto-detection failure is not an error - the mod scan is simply
        skipped for this run).
    """
    if override is not None:
        override_path = Path(override)

        if override_path.exists():
            return override_path

    for candidate in _mo2_plugins_txt_candidates():
        if candidate.exists():
            return candidate

    for candidate in _native_plugins_txt_candidates():
        if candidate.exists():
            return candidate

    return None


def parse_active_plugins(plugins_txt: Path) -> list[str]:
    """
    Parse a `Plugins.txt` into the list of currently active plugin filenames.

    Parameters
    ----------
    plugins_txt : Path
        Path to the `Plugins.txt` file.

    Returns
    -------
    list[str]
        Active plugin filenames (extension included), in file order. Lines
        starting with '#' are comments; a plugin line without a leading '*'
        is present but disabled and is excluded.
    """
    active: list[str] = []

    for line in plugins_txt.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("*"):
            active.append(stripped[1:].strip())

    return active


def resolve_ccc_path(game_directory: str) -> Path:
    """
    Get the path to the game's `<Game>.ccc` file.

    Lives in the game's own install root (sibling of `Data`), not in any
    mod-manager profile.

    Parameters
    ----------
    game_directory : str
        Path to the Skyrim game installation directory.

    Returns
    -------
    Path
        Path to `Skyrim.ccc` (existence not checked here).
    """
    return Path(game_directory) / "Skyrim.ccc"


def parse_ccc(ccc_path: Path) -> list[str]:
    """
    Parse a `<Game>.ccc` file into the list of auto-enabled Creation Club plugins.

    Skyrim SE loads every plugin listed here automatically, independently of
    `Plugins.txt` entirely - confirmed empirically: the in-game Creations
    menu showed a Creation Club pack as enabled even though it had no entry
    at all (active or disabled) in the MO2 profile's `Plugins.txt`, because
    MO2 only auto-lists Creation Club content as a "Not managed by MO2" mod
    entry (a priority-ordering artifact, unrelated to plugin activation) -
    `Skyrim.ccc` is the real source of truth for whether CC content loads.

    Parameters
    ----------
    ccc_path : Path
        Path to `Skyrim.ccc` (see `resolve_ccc_path`).

    Returns
    -------
    list[str]
        Plugin filenames, one per line, in file order. Empty if the file
        doesn't exist (not every install has Creation Club content).
    """
    if not ccc_path.exists():
        return []

    return [
        stripped
        for line in ccc_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if (stripped := line.strip())
    ]
