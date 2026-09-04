"""Minimal local stub for `sse_plugin_interface.subrecord` (see `plugin.pyi`)."""
from .datatypes import RawString

class Subrecord:
    type: str
    size: int
    data: bytes
    index: int | None

class StringSubrecord(Subrecord):
    string: RawString | int
