"""Isolated OCR microservice: decodes an uploaded image and runs Tesseract on it.

Defense in depth: performs its own magic-byte, size, and auth-token
validation independently of the main app - network isolation (no published
host port, internal-only Docker network) is the primary boundary, but this
service must not assume it will only ever be reached by the trusted app
container.
"""
import hmac
import io
import os
from typing import Annotated, TypedDict

import pytesseract
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pytesseract import Output

app = FastAPI(title="Skyrim OCR Service")


class TesseractDataDict(TypedDict):
    """
    Shape of `pytesseract.image_to_data`'s return value when `output_type=Output.DICT`.

    Defined locally (not imported from `pytesseract`, which has no such
    runtime type - it only exists as a type-checker stub in the main
    project's `typings/pytesseract/`) because FastAPI resolves this route's
    return annotation at startup to build its response model/OpenAPI schema,
    which requires a real, importable type.
    """

    level: list[int]
    page_num: list[int]
    block_num: list[int]
    par_num: list[int]
    line_num: list[int]
    word_num: list[int]
    left: list[int]
    top: list[int]
    width: list[int]
    height: list[int]
    conf: list[float]
    text: list[str]


class TesseractOcrResult(TypedDict):
    """
    Both OCR passes run against one screenshot.

    `binarized` is the primary pass (autocontrast + hard black/white
    threshold - recovers low-contrast rows rendered over a busy background,
    see `_BINARIZE_THRESHOLD`). `plain` is autocontrast only, with no
    threshold - kept as a second pass because binarizing occasionally
    corrupts a word that was perfectly legible without it (e.g. "Troll" was
    misread as "Teal" only after binarization, dropping "Troll Fat (3)"
    below the fuzzy-match cutoff entirely). Callers should treat `binarized`
    as authoritative and only pull additional names from `plain` that
    `binarized` missed - see `app.inventory._ocr.merge_ocr_matches`.
    """

    binarized: TesseractDataDict
    plain: TesseractDataDict

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Kept in sync with app/upload_validation.py's MAX_FILE_SIZE_BYTES in the main project.
_MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024

# Kept in sync with app/ocr_client.py's _BINARIZE_THRESHOLD in the main
# project - see that constant's comment for why a hard black/white
# threshold is applied after autocontrast (recovers inventory rows that
# render over a busy, low-contrast background and would otherwise be
# dropped entirely rather than misread).
_BINARIZE_THRESHOLD = 50


def _binarize_pixel(value: int) -> int:
    """
    Map one grayscale pixel to pure black or white at `_BINARIZE_THRESHOLD`.

    Parameters
    ----------
    value : int
        The pixel's grayscale value (0-255).

    Returns
    -------
    int
        255 (white) if above the threshold, else 0 (black).
    """
    return 255 if value > _BINARIZE_THRESHOLD else 0


def _check_auth(header_value: str | None) -> None:
    """
    Verify the shared internal auth token, in constant time.

    Parameters
    ----------
    header_value : str | None
        The `X-Internal-Auth` header value, if present.

    Raises
    ------
    HTTPException
        401 if the header is missing or doesn't match `OCR_SERVICE_TOKEN`.
    """
    expected = os.environ["OCR_SERVICE_TOKEN"]

    if header_value is None or not hmac.compare_digest(header_value, expected):
        raise HTTPException(401, detail="Invalid or missing internal auth token.")


@app.get("/health")
def health() -> dict[str, str]:
    """
    Perform a liveness/readiness check.

    Unauthenticated on purpose - the Docker HEALTHCHECK calls this without
    needing the internal auth token available in its CMD.

    Returns
    -------
    dict[str, str]
        Status payload.
    """
    return {"status": "ok"}


@app.post("/ocr")
async def ocr(
    image: Annotated[UploadFile, File()],
    x_internal_auth: Annotated[str | None, Header()] = None,
) -> TesseractOcrResult:
    """
    Decode an uploaded PNG and return both Tesseract OCR passes' output.

    Parameters
    ----------
    image : UploadFile
        The uploaded image (PNG only).
    x_internal_auth : str | None, optional
        Shared secret proving the caller is the trusted main app.

    Returns
    -------
    TesseractOcrResult
        Both passes' `image_to_data(..., output_type=Output.DICT)` output -
        see `TesseractOcrResult`'s docstring for why there are two.

    Raises
    ------
    HTTPException
        401 on a missing/invalid auth token, 413 if the image exceeds the
        size cap, 400 if it isn't a PNG or can't be decoded.
    """
    _check_auth(x_internal_auth)

    contents = await image.read()

    if len(contents) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, detail="Image exceeds maximum allowed size.")

    if contents[:8] != _PNG_MAGIC:
        raise HTTPException(400, detail="Only PNG images are accepted.")

    buffer = io.BytesIO(contents)

    try:
        # `.verify()` decodes and invalidates the Image object for further
        # use (documented Pillow behavior), hence the probe-then-reopen
        # pattern below. Image.MAX_IMAGE_PIXELS stays at Pillow's default -
        # never disabled - as the built-in decompression-bomb guard.
        with Image.open(buffer) as probe:
            probe.verify()

        buffer.seek(0)

        with Image.open(buffer) as img:
            processed = ImageOps.autocontrast(ImageOps.grayscale(img))
            binarized = Image.eval(processed, _binarize_pixel)

            return {
                "binarized": pytesseract.image_to_data(
                    binarized, lang="eng", output_type=Output.DICT
                ),
                "plain": pytesseract.image_to_data(
                    processed, lang="eng", output_type=Output.DICT
                ),
            }
    except UnidentifiedImageError:
        raise HTTPException(400, detail="Could not decode image.") from None
