"""
Parses Bethesda `.STRINGS` files and resolves a record's `FULL` value.

Neither `sse_plugin_interface` nor `sse_bsa` interprets `.STRINGS` content -
the plugin library hands back a raw localized string ID (an int), and the
BSA library hands back the raw bytes of the `.strings` file containing it.
This module is the glue between the two.
"""
import struct
from functools import lru_cache
from pathlib import Path

from app.game_data._bsa import extract_file, find_bsas_for_plugin


def parse_strings_file(data: bytes) -> dict[int, str]:
    """
    Parse a plain `.STRINGS` file's id -> text table.

    Note
    ----
    `FULL` never uses the `.DLSTRINGS`/`.ILSTRINGS` variants (those are for
    dialogue/item-description text, which length-prefix each string in
    addition to the id/offset table) - only this plain format applies here.

    Parameters
    ----------
    data : bytes
        Raw contents of a `.strings` file.

    Returns
    -------
    dict[int, str]
        String ID -> resolved text.
    """
    count, _data_size = struct.unpack_from("<II", data, 0)
    entries = struct.unpack_from(f"<{count * 2}I", data, 8)
    blob_start = 8 + count * 8

    table: dict[int, str] = {}

    for index in range(count):
        string_id = entries[2 * index]
        offset = entries[2 * index + 1]
        start = blob_start + offset
        end = data.index(b"\x00", start)
        table[string_id] = data[start:end].decode("utf-8", errors="replace")

    return table


@lru_cache(maxsize=None)
def _load_strings_table(plugin_path: Path, language: str) -> dict[int, str] | None:
    """
    Find and parse a plugin's `.strings` table for one language, cached.

    Parameters
    ----------
    plugin_path : Path
        Path to the plugin file.
    language : str
        Language suffix (e.g. "english").

    Returns
    -------
    dict[int, str] | None
        The parsed id -> text table, or None if no candidate BSA contains a
        matching `.strings` file.
    """
    archive_relative_name = f"strings/{plugin_path.stem.lower()}_{language}.strings"

    candidate_bsas = find_bsas_for_plugin(plugin_path)

    # Skyrim SE ships Dawnguard/HearthFires/Dragonborn/Update with no BSA of
    # their own at all - their strings (e.g. "strings/dawnguard_english.strings",
    # under the DLC's own stem, not Skyrim's) are bundled inside Skyrim.esm's
    # "Skyrim - Interface.bsa" instead. Fall back to Skyrim.esm's own BSAs
    # whenever the plugin's own stem-matched search comes up empty - this
    # covers that case without hardcoding a specific DLC filename.
    if not candidate_bsas:
        skyrim_esm = plugin_path.parent / "Skyrim.esm"

        if skyrim_esm != plugin_path and skyrim_esm.exists():
            candidate_bsas = find_bsas_for_plugin(skyrim_esm)

    for bsa_path in candidate_bsas:
        data = extract_file(bsa_path, archive_relative_name)

        if data is not None:
            return parse_strings_file(data)

    return None


def resolve_full(
    full_raw: str | int | None,
    plugin_path: Path,
    language: str = "english",
) -> str | None:
    """
    Resolve a record's raw `FULL` value to display text.

    Parameters
    ----------
    full_raw : str | int | None
        The raw value from `app.game_data._plugin_records.get_full_raw` - literal
        text, a localized string ID, or None (no `FULL` subrecord at all).
    plugin_path : Path
        Path to the plugin the record came from (used to locate its BSA
        when `full_raw` is a string ID).
    language : str, optional
        Language to resolve against, by default "english".

    Returns
    -------
    str | None
        The resolved display text, or None if it couldn't be resolved
        (no `FULL` subrecord, or the string ID wasn't found in any of the
        plugin's BSAs).
    """
    if full_raw is None:
        return None

    if isinstance(full_raw, str):
        return full_raw

    table = _load_strings_table(plugin_path, language)

    if table is None:
        return None

    return table.get(full_raw)
