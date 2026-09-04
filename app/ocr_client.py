"""OCR backend selection: the isolated `ocr` container, or local Tesseract as a fallback.

The API's upload path (`app/api.py`) always calls `run_remote_ocr` directly
and never falls back - it deliberately never runs Tesseract in-process, so
the untrusted, user-uploaded image bytes are only ever decoded inside the
`ocr` service's isolated container.

The CLI (`app/inventory/_ocr.py`) instead goes through `run_ocr`, which lets
someone run the CLI without installing Tesseract on their system at all:
if the `ocr` container (see `docker-compose.ocr.yml`) is reachable, it's
used exactly like the API uses it; otherwise, a local Tesseract install is
tried; if neither is available, `OcrUnavailableError` is raised.
"""
import io
import os
import shutil
from functools import lru_cache
from typing import Literal, TypedDict

import pytesseract
import requests
from PIL import Image, ImageOps
from pytesseract import Output

from app.i18n import translate


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

    Duplicated from `ocr_service/main.py`'s identical definition - kept in
    sync across the isolated container boundary, same as `_BINARIZE_THRESHOLD`.
    """

    binarized: pytesseract.TesseractDataDict
    plain: pytesseract.TesseractDataDict

# Base URL of the isolated `ocr` service, no path. Defaults to the CLI's
# un-containerized case - `localhost` with the port `docker-compose.ocr.yml`
# publishes to the host. The containerized `app` service overrides this via
# the `OCR_SERVICE_URL` env var (see `docker-compose.yml`) to reach `ocr` by
# its internal-network DNS name instead.
OCR_SERVICE_BASE_URL = os.environ.get("OCR_SERVICE_URL", "http://localhost:9000")
_REQUEST_TIMEOUT_SECONDS = 30.0
_HEALTH_CHECK_TIMEOUT_SECONDS = 1.5

# Grayscale value (0-255, after autocontrast) below which a pixel is treated
# as text ink rather than background. Some inventory rows render over a
# busy, dark character-portrait background instead of the plain menu
# background, and their grey (unselected-row) text ends up low-contrast
# enough that Tesseract detects the row as one paragraph block but extracts
# no legible characters from it at all (e.g. "Sabre Cat Tooth (3)" and
# "Salt Pile (137)" were silently dropped entirely, not misread). A hard
# black/white threshold after autocontrast recovers them; empirically,
# values in this range don't lose or corrupt any row that autocontrast
# alone already reads correctly.
_BINARIZE_THRESHOLD = 50

_OcrBackend = Literal["container", "local"]


class OcrServiceError(Exception):
    """Raised when the OCR microservice is unreachable or returns a non-2xx response."""


class OcrUnavailableError(Exception):
    """Raised when neither the `ocr` container nor a local Tesseract install is usable."""


def is_ocr_service_available() -> bool:
    """
    Probe the `ocr` service's health endpoint with a short timeout.

    Only used by the CLI's `run_ocr` dispatch - the API always requires the
    container and never probes for it (see `run_remote_ocr`).

    Returns
    -------
    bool
        True if the service answered successfully within the timeout.
    """
    try:
        response = requests.get(
            f"{OCR_SERVICE_BASE_URL}/health", timeout=_HEALTH_CHECK_TIMEOUT_SECONDS
        )
    except requests.RequestException:
        return False

    return response.ok


def is_local_tesseract_available() -> bool:
    """
    Check whether a `tesseract` binary is installed and resolvable via PATH.

    Only checks the default `tesseract` command name - doesn't account for a
    custom `pytesseract.pytesseract.tesseract_cmd` override, which covers
    the install path documented in the README's Requirements section.

    Returns
    -------
    bool
        True if `tesseract` is on PATH.
    """
    return shutil.which("tesseract") is not None


def run_remote_ocr(image_bytes: bytes, filename: str) -> TesseractOcrResult:
    """
    Send image bytes to the isolated OCR service and return both its OCR passes.

    Parameters
    ----------
    image_bytes : bytes
        Already-validated PNG bytes.
    filename : str
        Original filename, forwarded as the multipart part's filename.

    Returns
    -------
    TesseractOcrResult
        The OCR service's structured OCR output, both passes.

    Raises
    ------
    OcrServiceError
        If the request fails, times out, or the service returns an error status.
    """
    token = os.environ.get("OCR_SERVICE_TOKEN", "")

    try:
        response = requests.post(
            f"{OCR_SERVICE_BASE_URL}/ocr",
            files={"image": (filename, image_bytes, "image/png")},
            headers={"X-Internal-Auth": token},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as request_error:
        raise OcrServiceError(
            f"OCR service request failed for '{filename}': {request_error}"
        ) from request_error

    return response.json()


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


def _run_local_tesseract(image_bytes: bytes) -> TesseractOcrResult:
    """
    Run Tesseract in-process against raw image bytes, both passes.

    Parameters
    ----------
    image_bytes : bytes
        Raw screenshot image bytes (PNG).

    Returns
    -------
    TesseractOcrResult
        Tesseract's structured OCR output, both passes.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        processed = ImageOps.autocontrast(ImageOps.grayscale(img))
        # `Image.eval` (a thin `image.point()` wrapper with a single,
        # unambiguous `Callable[[int], float]` signature) instead of calling
        # `.point()` directly - `.point`'s own overloads include a
        # `NumpyArray` branch that pyright can't resolve without numpy
        # installed (not a dependency of this project), which taints the
        # whole overload set as partially Unknown under strict mode.
        binarized = Image.eval(processed, _binarize_pixel)

        return {
            "binarized": pytesseract.image_to_data(
                binarized, lang="eng", output_type=Output.DICT
            ),
            "plain": pytesseract.image_to_data(
                processed, lang="eng", output_type=Output.DICT
            ),
        }


@lru_cache
def _resolve_ocr_backend() -> _OcrBackend:
    """
    Decide which OCR backend this process will use, announcing the choice once.

    Cached for the process's lifetime: a CLI run is short enough that the
    container's availability won't change mid-run, and caching avoids both a
    repeated health-check probe and a duplicate console message for every
    screenshot that needs OCR.

    Returns
    -------
    _OcrBackend
        `"container"` if the `ocr` service answered its health check,
        `"local"` if not but a local Tesseract install is on PATH.

    Raises
    ------
    OcrUnavailableError
        If neither is available.
    """
    if is_ocr_service_available():
        print(translate("ocr_using_container"))
        return "container"

    if is_local_tesseract_available():
        print(translate("ocr_using_local_tesseract"))
        return "local"

    raise OcrUnavailableError(translate("ocr_unavailable"))


def run_ocr(image_bytes: bytes, filename: str) -> TesseractOcrResult:
    """
    Run OCR via the `ocr` container when reachable, else a local Tesseract install.

    CLI-only dispatch (`app/inventory/_ocr.py`) - see this module's
    docstring for why the API never calls this.

    Parameters
    ----------
    image_bytes : bytes
        Raw screenshot image bytes (PNG).
    filename : str
        Original filename, forwarded to the service if that backend is used.

    Returns
    -------
    TesseractOcrResult
        Tesseract's structured OCR output, both passes, from whichever
        backend ran.

    Raises
    ------
    OcrUnavailableError
        If neither the `ocr` container nor a local Tesseract install is usable.
    """
    backend = _resolve_ocr_backend()

    if backend == "container":
        try:
            return run_remote_ocr(image_bytes, filename)
        except OcrServiceError as service_error:
            # The health check passed but the real request still failed (e.g. it
            # went down in between) - fall back for this one image rather than
            # aborting the whole run, but don't update the cached backend: a
            # transient failure shouldn't permanently downgrade every
            # subsequent screenshot in this same run.
            if is_local_tesseract_available():
                print(translate("ocr_container_failed_falling_back"))
                return _run_local_tesseract(image_bytes)

            raise OcrUnavailableError(translate("ocr_unavailable")) from service_error

    return _run_local_tesseract(image_bytes)
