"""HTTP client for the isolated OCR microservice (used only by the upload API path)."""
import os

import pytesseract
import requests

OCR_SERVICE_URL = "http://ocr:9000/ocr"
_TIMEOUT_SECONDS = 30.0


class OcrServiceError(Exception):
    """Raised when the OCR microservice is unreachable or returns a non-2xx response."""


def run_remote_ocr(image_bytes: bytes, filename: str) -> pytesseract.TesseractDataDict:
    """
    Send image bytes to the isolated OCR service and return its structured OCR output.

    The main app never decodes the (untrusted, user-uploaded) image bytes
    itself - Tesseract and Pillow both run only inside the `ocr` service's
    isolated, internal-network-only container.

    Parameters
    ----------
    image_bytes : bytes
        Already-validated PNG bytes.
    filename : str
        Original filename, forwarded as the multipart part's filename.

    Returns
    -------
    TesseractDataDict
        The OCR service's structured OCR output.

    Raises
    ------
    OcrServiceError
        If the request fails, times out, or the service returns an error status.
    """
    token = os.environ["OCR_SERVICE_TOKEN"]

    try:
        response = requests.post(
            OCR_SERVICE_URL,
            files={"image": (filename, image_bytes, "image/png")},
            headers={"X-Internal-Auth": token},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as request_error:
        raise OcrServiceError(
            f"OCR service request failed for '{filename}': {request_error}"
        ) from request_error

    return response.json()
