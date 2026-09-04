"""Minimal local stub for `sse_plugin_interface.record` (see `plugin.pyi`)."""
from .subrecord import Subrecord

class Record:
    type: str
    size: int
    formid: str
    timestamp: int
    version_control_info: int
    internal_version: int
    unknown: int
    data: bytes
    subrecords: list[Subrecord]

    def __len__(self) -> int: ...
