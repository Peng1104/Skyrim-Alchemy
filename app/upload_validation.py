"""Validation for user-uploaded screenshot files (API upload path only).

Security note: the main app never hands uploaded bytes to any image-parsing
library itself (that happens only inside the isolated `ocr` service) - this
module's job is strictly the cheap, magic-byte-level checks that let the API
reject obviously-bad input before it's ever forwarded anywhere.
"""
from dataclasses import dataclass
from typing import Literal

from fastapi import UploadFile

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# ~15MB - generous for a 4K PNG screenshot (typically a few MB), while still
# bounding worst-case memory/network cost per file.
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024

# A full scrolled inventory rarely spans more than a handful of screenshots;
# this caps worst-case OCR-service load (and request duration) per request.
MAX_FILE_COUNT = 20

ValidationReason = Literal["too_many_files", "invalid_type", "too_large"]


@dataclass(frozen=True)
class ValidationError:
    """One upload batch validation failure - the whole batch is rejected on the first one."""

    filename: str
    reason: ValidationReason


def _read_magic_bytes(upload: UploadFile) -> bytes:
    """
    Read the first 8 bytes of an uploaded file without consuming its stream.

    Parameters
    ----------
    upload : UploadFile
        The uploaded file.

    Returns
    -------
    bytes
        The file's first 8 bytes (or fewer, if the file is shorter).
    """
    header = upload.file.read(8)
    upload.file.seek(0)

    return header


def validate_upload_batch(files: list[UploadFile]) -> ValidationError | None:
    """
    Validate every file in an upload batch; return the first failure, if any.

    Checks, in order: file count cap, PNG magic bytes (read before any
    image-parsing library ever touches the bytes), then size cap.

    Parameters
    ----------
    files : list[UploadFile]
        The uploaded files.

    Returns
    -------
    ValidationError | None
        None if every file passed; the first failure encountered otherwise.
    """
    if len(files) > MAX_FILE_COUNT:
        return ValidationError(
            filename=files[MAX_FILE_COUNT].filename or "", reason="too_many_files"
        )

    for upload in files:
        filename = upload.filename or "<unnamed>"

        if _read_magic_bytes(upload) != _PNG_MAGIC:
            return ValidationError(filename=filename, reason="invalid_type")

        if upload.size is not None and upload.size > MAX_FILE_SIZE_BYTES:
            return ValidationError(filename=filename, reason="too_large")

    return None
