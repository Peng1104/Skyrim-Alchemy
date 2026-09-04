"""
Minimal local stub for `sse_plugin_interface` (installed 1.0.1).

The real package has no `py.typed` marker, so pyright infers `Unknown` for
its untyped source. This stub covers only what this project actually calls:
`SSEPlugin.from_file`, `SSEPlugin.extract_group_records`,
`SSEPlugin.get_record_edid`, and the parsed `TES4` master list / group tree
- the latter two only reachable through the library's own name-mangled
private attributes (`_SSEPlugin__masters`/`_SSEPlugin__groups`), since the
installed version exposes no public getter for either. Declaring them here
(as plain attributes matching their mangled names) is what lets
`app/mods/_plugin_records.py` read them under `pyright --strict` without a
suppression comment - the mangling itself is unavoidable until upstream
adds a public accessor.
"""
from pathlib import Path
from typing import Self

from .datatypes import RawString
from .group import Group
from .record import Record

class SSEPlugin:
    _SSEPlugin__plugin_name: str
    _SSEPlugin__masters: list[RawString]
    _SSEPlugin__groups: list[Group]

    def __init__(self, name: str) -> None: ...
    @classmethod
    def from_file(cls, path: Path) -> Self: ...
    @staticmethod
    def get_record_edid(record: Record) -> RawString | None: ...
    @staticmethod
    def extract_group_records(group: Group, recursive: bool = ...) -> list[Record]: ...
