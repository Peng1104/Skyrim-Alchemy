"""OCR extraction of ingredient name/amount pairs from a Skyrim inventory screenshot."""
import re

import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output
from rapidfuzz import fuzz, process

from app.models import InventoryIngredient

# No trailing anchor: rows near the item tooltip get OCR'd merged with tooltip
# text on the same line (e.g. "Tundra Cotton (91) UNKNOWN UNKNOWN") - matching
# only the leading "Name (amount)" prefix recovers those instead of dropping them.
# A short leading run of non-letter junk is also skipped - the category list's
# scroll-arrow icon next to the selected row (e.g. "|)") sometimes gets OCR'd
# onto the very start of the item column's segment, and would otherwise block
# the match entirely since it isn't a letter.
_LINE_PATTERN = re.compile(
    r"^[^A-Za-z]{0,10}(?P<name>[A-Za-z][A-Za-z'\- ]*[A-Za-z])(?:\s*\((?P<amount>\d+)\))?"
)
_FUZZY_SCORE_CUTOFF = 82
_MIN_NAME_LENGTH = 3

# Words after the matched "Name (amount)" prefix that mark the segment as a
# transient HUD message (e.g. "Gold (14) Removed") rather than an inventory
# row - these can fuzzy-match a real ingredient name by coincidence (e.g.
# "Gold" scores 90 against "Gold Kanet") and must never be kept.
_NOTIFICATION_KEYWORDS = ("removed", "added")

# Horizontal gap (in pixels) between two consecutive OCR'd words on the same
# detected line that signals they actually belong to two unrelated UI columns
# (e.g. a HUD notification on the left and the item list on the right) which
# Tesseract merged into a single line. Splitting on it keeps each column's
# text independent, instead of losing the second column to the line pattern's
# leading-prefix match on the first.
_COLUMN_GAP_THRESHOLD = 60


def _line_segments(data: pytesseract.TesseractDataDict) -> list[str]:
    """
    Group OCR'd words into per-line text segments, split by UI column.

    Parameters
    ----------
    data : pytesseract.TesseractDataDict
        Output of `pytesseract.image_to_data(..., output_type=Output.DICT)`.

    Returns
    -------
    list[str]
        Reassembled text segments - one per detected line, further split
        wherever a large horizontal gap indicates two merged UI columns.
    """
    segments: list[str] = []
    current_words: list[str] = []
    prev_right: int | None = None
    prev_key: tuple[int, int, int] | None = None

    for i in range(len(data["text"])):
        word = data["text"][i].strip()

        if not word:
            continue

        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        left = data["left"][i]
        right = left + data["width"][i]

        starts_new_segment = (
            key != prev_key
            or prev_right is None
            or left - prev_right > _COLUMN_GAP_THRESHOLD
        )

        if starts_new_segment and current_words:
            segments.append(" ".join(current_words))
            current_words = []

        current_words.append(word)
        prev_right = right
        prev_key = key

    if current_words:
        segments.append(" ".join(current_words))

    return segments


def extract_ingredients_from_image(
    img: Image.Image, known_names: list[str]
) -> list[InventoryIngredient]:
    """
    Run OCR on a screenshot and fuzzy-match recognized lines against known ingredient names.

    Parameters
    ----------
    img : Image.Image
        Screenshot image to analyze.
    known_names : list[str]
        Whitelist of valid ingredient names to match OCR text against.

    Returns
    -------
    list[InventoryIngredient]
        Ingredients recognized with high enough confidence.
    """
    processed = ImageOps.autocontrast(ImageOps.grayscale(img))
    data = pytesseract.image_to_data(processed, lang="eng", output_type=Output.DICT)

    ingredients: list[InventoryIngredient] = []

    for segment in _line_segments(data):
        segment = segment.strip()
        match = _LINE_PATTERN.match(segment)

        if not match:
            continue

        name_candidate: str = match.group("name")
        amount_candidate: str | None = match.group("amount")

        if len(name_candidate) < _MIN_NAME_LENGTH:
            # Rejects short OCR noise fragments (stray glyphs, UI corner
            # decorations) that can otherwise fuzzy-match a real ingredient
            # by coincidence - e.g. "ri" scoring 90 against "Briar Heart".
            continue

        remainder = segment[match.end():].strip().lower()

        if any(keyword in remainder for keyword in _NOTIFICATION_KEYWORDS):
            continue

        best_match = process.extractOne(
            name_candidate,
            known_names,
            scorer=fuzz.WRatio,
            score_cutoff=_FUZZY_SCORE_CUTOFF,
        )

        if best_match is None:
            continue

        ingredients.append(InventoryIngredient(
            name=best_match[0],
            amount=int(amount_candidate) if amount_candidate is not None else 1,
        ))

    return ingredients
