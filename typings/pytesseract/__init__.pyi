"""
Minimal local stub for `pytesseract`.

pytesseract ships no `py.typed` marker and there is no `types-pytesseract`
package on PyPI (checked - 404), so pyright infers `Unknown` for its
untyped source. This stub covers only what this project actually calls
(`image_to_string` with the default string output, `image_to_data` with
`Output.DICT`), typed accurately against the installed 0.3.13 source
(`pytesseract/pytesseract.py`).
"""
from typing import TypedDict

from PIL.Image import Image

class Output:
    BYTES: str
    DATAFRAME: str
    DICT: str
    STRING: str

class TesseractDataDict(TypedDict):
    """Shape of `image_to_data`'s return value when `output_type=Output.DICT`."""

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

def image_to_string(
    image: Image | str,
    lang: str | None = ...,
    config: str = ...,
    nice: int = ...,
    output_type: str = ...,
    timeout: int = ...,
) -> str: ...
def image_to_data(
    image: Image | str,
    lang: str | None = ...,
    config: str = ...,
    nice: int = ...,
    output_type: str = ...,
    timeout: int = ...,
    pandas_config: dict[str, object] | None = ...,
) -> TesseractDataDict: ...
