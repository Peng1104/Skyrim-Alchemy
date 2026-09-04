"""
Thin wrapper over `sse_plugin_interface` for reading `.esp/.esm/.esl` records.

Only what this project needs: masters/override detection, `INGR` ingredient
records (name + the 4 effect FormIDs + their per-ingredient magnitude/area/
duration), and `MGEF` magic effect records (name + raw `DATA` stats). The
library itself has no public getter for the parsed master list (it's a
name-mangled private attribute), so `get_masters` reaches into it directly -
isolated here so a future library version only needs one function fixed.
"""
import struct
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sse_plugin_interface.plugin import SSEPlugin
from sse_plugin_interface.record import Record


@lru_cache(maxsize=None)
def load_plugin(plugin_path: Path) -> SSEPlugin:
    """
    Parse a `.esp/.esm/.esl` file, cached by path.

    A scan resolves many `EFID`s back into the same handful of master files
    (`Skyrim.esm` in particular) - caching avoids re-parsing a ~250 MB master
    once per effect reference.

    Parameters
    ----------
    plugin_path : Path
        Path to the plugin file.

    Returns
    -------
    SSEPlugin
        The parsed plugin.
    """
    return SSEPlugin.from_file(plugin_path)


@lru_cache(maxsize=None)
def _mgef_index(plugin_path: Path) -> dict[int, Record]:
    """
    Build (and cache) a plugin's `MGEF` records indexed by local FormID.

    Parameters
    ----------
    plugin_path : Path
        Path to the plugin file.

    Returns
    -------
    dict[int, Record]
        Record-local id (the FormID's low 3 bytes) -> `MGEF` record.
    """
    plugin = load_plugin(plugin_path)

    return {
        int(record.formid, base=16) & 0xFFFFFF: record
        for record in iter_records_of_type(plugin, "MGEF")
    }


def find_mgef(plugin_path: Path, local_id: int) -> Record | None:
    """
    Find an `MGEF` record by its record-local id within one plugin.

    Parameters
    ----------
    plugin_path : Path
        Path to the plugin that defines the record (the file resolved by
        `resolve_form_id`).
    local_id : int
        The record-local id (the FormID's low 3 bytes).

    Returns
    -------
    Record | None
        The matching `MGEF` record, or None if not found (e.g. a malformed
        reference).
    """
    return _mgef_index(plugin_path).get(local_id)


def get_masters(plugin: SSEPlugin) -> list[str]:
    """
    Get a plugin's master file list, in load order.

    Parameters
    ----------
    plugin : SSEPlugin
        The parsed plugin.

    Returns
    -------
    list[str]
        Master filenames, in the order declared in the plugin's TES4 header.
    """
    return [str(master) for master in plugin._SSEPlugin__masters]  # noqa: SLF001


def iter_records_of_type(plugin: SSEPlugin, record_type: str) -> Iterator[Record]:
    """
    Iterate every record of a given type in a plugin, across all groups.

    Parameters
    ----------
    plugin : SSEPlugin
        The parsed plugin.
    record_type : str
        Four-letter record signature to filter on (e.g. "INGR", "MGEF").

    Returns
    -------
    Iterator[Record]
        Matching records, in file order. Traverses nested GRUPs.
    """
    for group in plugin._SSEPlugin__groups:  # noqa: SLF001
        for record in SSEPlugin.extract_group_records(group):
            if record.type == record_type:
                yield record


def is_new_record(record: Record, masters: list[str]) -> bool:
    """
    Determine whether a record is newly defined by its own plugin.

    Parameters
    ----------
    record : Record
        The record to check.
    masters : list[str]
        The plugin's master list (see `get_masters`).

    Returns
    -------
    bool
        True if the record's FormID top byte falls outside the master
        list's range (defined by this plugin), False if it's an override of
        a record first defined in one of the masters.
    """
    return int(record.formid[:2], base=16) >= len(masters)


def resolve_form_id(form_id: int, masters: list[str], own_filename: str) -> tuple[str, int]:
    """
    Resolve a FormID to the file that actually defines it, and its local id.

    Parameters
    ----------
    form_id : int
        The FormID to resolve (e.g. from an `EFID` subrecord).
    masters : list[str]
        The referencing plugin's master list (see `get_masters`).
    own_filename : str
        The referencing plugin's own filename, used when the FormID is a
        self-reference (defined by this same plugin, not a master).

    Returns
    -------
    tuple[str, int]
        (defining file's name, record-local id - the FormID's low 3 bytes).
    """
    master_index = form_id >> 24
    local_id = form_id & 0xFFFFFF

    if master_index < len(masters):
        return masters[master_index], local_id

    return own_filename, local_id


def get_edid(record: Record) -> str | None:
    """
    Get a record's Editor ID.

    Parameters
    ----------
    record : Record
        The record to inspect.

    Returns
    -------
    str | None
        The Editor ID, or None if the record has no `EDID` subrecord.
    """
    edid = SSEPlugin.get_record_edid(record)

    return str(edid) if edid is not None else None


def get_full_raw(record: Record) -> str | int | None:
    """
    Get a record's `FULL` (display name) subrecord value, unresolved.

    Parameters
    ----------
    record : Record
        The record to inspect (`INGR` or `MGEF`).

    Returns
    -------
    str | int | None
        Literal display text, or the localized string ID (int) if the
        plugin is localized, or None if there's no `FULL` subrecord.
    """
    for subrecord in record.subrecords:
        if subrecord.type == "FULL":
            string = getattr(subrecord, "string", None)

            if isinstance(string, int):
                return string
            if string is not None:
                return str(string)

    return None


def get_effect_entries(record: Record) -> list[tuple[int, tuple[float, int, int]]]:
    """
    Get an `INGR` record's 4 effects, each paired with its own use-data.

    Parameters
    ----------
    record : Record
        An `INGR` record.

    Returns
    -------
    list[tuple[int, tuple[float, int, int]]]
        `(effect_form_id, (magnitude, area, duration))` per effect, in
        subrecord order - `EFIT` always immediately follows its `EFID`.
    """
    entries: list[tuple[int, tuple[float, int, int]]] = []
    subrecords = record.subrecords

    for index, subrecord in enumerate(subrecords):
        if subrecord.type != "EFID":
            continue

        (form_id,) = struct.unpack_from("<I", subrecord.data, 0)

        magnitude, area, duration = 0.0, 0, 0
        if index + 1 < len(subrecords) and subrecords[index + 1].type == "EFIT":
            efit_data = subrecords[index + 1].data
            magnitude, area, duration = struct.unpack_from("<fII", efit_data, 0)

        entries.append((form_id, (magnitude, area, duration)))

    return entries


def get_mgef_base_cost(record: Record) -> float | None:
    """
    Get an `MGEF` record's base cost, from its `DATA` subrecord.

    Parameters
    ----------
    record : Record
        An `MGEF` record.

    Returns
    -------
    float | None
        The base cost (always at byte offset 4 of `DATA`, right after the
        4-byte Flags field - present even in the shortest legacy variant of
        the struct), or None if the record has no `DATA` subrecord.
    """
    for subrecord in record.subrecords:
        if subrecord.type == "DATA":
            (base_cost,) = struct.unpack_from("<f", subrecord.data, 4)

            return base_cost

    return None


# Bit positions within DATA's Flags field (offset 0, u32 LE) - per
# Core/wbDefinitionsTES5.pas in the xEdit source (the same reference used
# for the rest of this MGEF DATA layout).
_MGEF_FLAG_HOSTILE = 0x01
_MGEF_FLAG_DETRIMENTAL = 0x04


def get_mgef_harmful(record: Record) -> bool:
    """
    Get whether an `MGEF` record is harmful (poison-type), from its `DATA` flags.

    Validated against all 205 UESP-known effects that also resolve in
    `Skyrim.esm`: `Detrimental` alone mismatches UESP's own harmful/beneficial
    classification on 2 (`Paralysis`, `Fear` - marked `Hostile` but not
    `Detrimental`); `Detrimental OR Hostile` matches all 205 with zero
    mismatches, so that's the rule used here.

    Parameters
    ----------
    record : Record
        An `MGEF` record.

    Returns
    -------
    bool
        True if either the `Hostile` or `Detrimental` flag bit is set.
        False (not True, unlike `get_mgef_base_cost`'s `None`) if the record
        has no `DATA` subrecord - matches `Effect.harmful`'s own default.
    """
    for subrecord in record.subrecords:
        if subrecord.type == "DATA":
            (flags,) = struct.unpack_from("<I", subrecord.data, 0)

            return bool(flags & (_MGEF_FLAG_HOSTILE | _MGEF_FLAG_DETRIMENTAL))

    return False
