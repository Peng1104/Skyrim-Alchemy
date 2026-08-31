"""
Minimal local stub for `pytesseract`.

pytesseract ships no `py.typed` marker and there is no `types-pytesseract`
package on PyPI (checked - 404), so pyright infers `Unknown` for its
untyped source. This stub covers only what this project actually calls
(`image_to_string` with the default string output), typed accurately
against the installed 0.3.13 source (`pytesseract/pytesseract.py`).
"""
from PIL.Image import Image

class Output:
    BYTES: str
    DATAFRAME: str
    DICT: str
    STRING: str

def image_to_string(
    image: Image | str,
    lang: str | None = ...,
    config: str = ...,
    nice: int = ...,
    output_type: str = ...,
    timeout: int = ...,
) -> str: ...
