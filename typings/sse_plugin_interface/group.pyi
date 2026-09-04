"""Minimal local stub for `sse_plugin_interface.group` (see `plugin.pyi`)."""
from .record import Record

class Group:
    type: str
    group_size: int
    group_type: int
    children: list[Group | Record]

    def __len__(self) -> int: ...
