"""Thin wrapper over `sse_bsa` for extracting a file by name from a `.bsa`."""
from functools import lru_cache
from pathlib import Path

from sse_bsa import BSAArchive


@lru_cache(maxsize=None)
def _open_archive(bsa_path: Path) -> BSAArchive:
    """
    Open (and cache) a `.bsa` archive's parsed header/file table.

    Parameters
    ----------
    bsa_path : Path
        Path to the `.bsa` archive.

    Returns
    -------
    BSAArchive
        The parsed archive, reused across repeated calls for the same path -
        a scan touches the same handful of archives (e.g. one per plugin's
        strings) many times, once per ingredient/effect resolved.
    """
    return BSAArchive(bsa_path)


def find_bsas_for_plugin(plugin_path: Path) -> list[Path]:
    """
    Find every `.bsa` archive associated with a plugin.

    Matches by filename prefix (case-insensitive), covering both the
    single-archive convention (`<stem>.bsa`) and the split convention
    (`<stem> - Main.bsa`, `<stem> - Textures.bsa`, etc.).

    Parameters
    ----------
    plugin_path : Path
        Path to the plugin file (`.esp`/`.esm`/`.esl`).

    Returns
    -------
    list[Path]
        Matching `.bsa` paths in the plugin's own directory. Empty if the
        plugin has none (loose-file or literal-text-only mods).
    """
    stem = plugin_path.stem.lower()

    return [
        candidate
        for candidate in plugin_path.parent.glob("*.bsa")
        if candidate.stem.lower().startswith(stem)
    ]


def extract_file(bsa_path: Path, archive_relative_name: str) -> bytes | None:
    """
    Extract one file's raw bytes from a `.bsa` archive.

    Parameters
    ----------
    bsa_path : Path
        Path to the `.bsa` archive.
    archive_relative_name : str
        The file's path inside the archive (e.g.
        "strings/ccbgssse037-curios_english.strings").

    Returns
    -------
    bytes | None
        The file's raw bytes, or None if the archive doesn't contain it.
    """
    archive = _open_archive(bsa_path)

    try:
        return archive.get_file_stream(archive_relative_name).read()
    except FileNotFoundError:
        return None
