"""OCR extraction of ingredient name/amount pairs from a Skyrim inventory screenshot."""
import re

import pytesseract
from PIL import Image, ImageOps
from rapidfuzz import fuzz, process

from app.models import InventoryIngredient

# No trailing anchor: rows near the item tooltip get OCR'd merged with tooltip
# text on the same line (e.g. "Tundra Cotton (91) UNKNOWN UNKNOWN") - matching
# only the leading "Name (amount)" prefix recovers those instead of dropping them.
_LINE_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z'\- ]*[A-Za-z])(?:\s*\((?P<amount>\d+)\))?"
)
_FUZZY_SCORE_CUTOFF = 82
_MIN_NAME_LENGTH = 3


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
    text = pytesseract.image_to_string(processed, lang="eng")

    ingredients: list[InventoryIngredient] = []

    for line in text.splitlines():
        match = _LINE_PATTERN.match(line.strip())

        if not match:
            continue

        name_candidate: str = match.group("name")
        amount_candidate: str | None = match.group("amount")

        if len(name_candidate) < _MIN_NAME_LENGTH:
            # Rejects short OCR noise fragments (stray glyphs, UI corner
            # decorations) that can otherwise fuzzy-match a real ingredient
            # by coincidence - e.g. "ri" scoring 90 against "Briar Heart".
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
