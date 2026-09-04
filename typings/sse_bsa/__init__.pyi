"""
Minimal local stub for `sse_bsa` (installed 1.1.0).

The real package has no `py.typed` marker, so pyright infers `Unknown` for
its untyped source. This stub covers only what this project actually calls
(`BSAArchive.__init__` and `.get_file_stream`), typed accurately against
the installed source (`sse_bsa/bsa_archive.py`).
"""
from io import BytesIO
from pathlib import Path

class BSAArchive:
    def __init__(self, archive_path: Path) -> None: ...
    @property
    def files(self) -> list[Path]: ...
    def glob(self, pattern: str) -> list[str]: ...
    def get_file_stream(self, filename: str | Path) -> BytesIO: ...
