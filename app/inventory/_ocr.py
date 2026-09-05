"""OCR extraction of ingredient name/amount pairs from a Skyrim inventory screenshot."""
import re
import unicodedata

import pytesseract
from rapidfuzz import fuzz, process

from app.models import InventoryIngredient
from app.ocr_client import run_ocr

# No trailing anchor: rows near the item tooltip get OCR'd merged with tooltip
# text on the same line (e.g. "Tundra Cotton (91) UNKNOWN UNKNOWN") - matching
# only the leading "Name (amount)" prefix recovers those instead of dropping them.
# A short leading run of non-letter junk is also skipped - the category list's
# scroll-arrow icon next to the selected row (e.g. "|)") sometimes gets OCR'd
# onto the very start of the item column's segment, and would otherwise block
# the match entirely since it isn't a letter.
#
# The apostrophe class includes both the straight quote (') and the Unicode
# right single quotation mark (', U+2019) - Tesseract inconsistently picks
# one or the other for the same glyph across screenshots of the same
# ingredient (e.g. "Chicken's Egg" reads with ' in one screenshot and ' in
# another), and only matching ' would cut the name short there, leaving the
# amount group unmatched and silently defaulting to 1 instead of the real count.
#
# The amount group also accepts a leading '}' in place of a digit - Tesseract
# occasionally misreads a leading "1" (e.g. in "(10)") as a curly brace in
# this font, and without this the amount group fails to match at all and
# silently falls back to 1 instead of the real count. Normalized back to "1"
# by `_parse_amount` before parsing.
#
# The closing ')' is optional - on a row whose background is low-contrast
# enough to need `_binarize` (see that function), the closing paren is thin
# enough to occasionally vanish in the black/white threshold, leaving e.g.
# "Sabre Cat Tooth (3" with no ')'. Requiring it would drop the amount group
# entirely and silently fall back to 1 instead of the real count.
_LINE_PATTERN = re.compile(
    r"^[^A-Za-z]{0,10}(?P<name>[A-Za-z][A-Za-z'’\- ]*[A-Za-z])(?:\s*\((?P<amount>[}\d]\d*)\)?)?"
)
_FUZZY_SCORE_CUTOFF = 82
_MIN_NAME_LENGTH = 3

# Words after the matched "Name (amount)" prefix that mark the segment as a
# transient HUD message (e.g. "Gold (14) Removed") rather than an inventory
# row - these can fuzzy-match a real ingredient name by coincidence (e.g.
# "Gold" scores 90 against "Gold Kanet") and must never be kept.
_NOTIFICATION_KEYWORDS = ("removed", "added")

# Persistent (not transient) HUD chrome text that can appear as its own OCR
# segment with no amount and no _NOTIFICATION_KEYWORDS attached - e.g. the
# "Carry Weight X/Y  Gold Z" bar at the bottom of the inventory screen can
# OCR "Gold" as an isolated word, which then fuzzy-matches the real
# ingredient "Gold Kanet" (score 90) and is wrongly counted as 1 owned.
# Likewise the "A Add  B Exit" button prompt row present on every inventory
# screen: post-`_binarize` its "Add"/"Exit" OCR cleanly and short, and
# WRatio's partial-ratio scoring can put a 3-4 letter word above
# `_FUZZY_SCORE_CUTOFF` against an unrelated long ingredient name by
# coincidence (e.g. "add" scores 90 against "Red Kelp Gas Bladder").
_UI_CHROME_NAMES = frozenset({"gold", "add", "exit"})

# Horizontal gap (in pixels) between two consecutive OCR'd words on the same
# detected line that signals they actually belong to two unrelated UI columns
# (e.g. a HUD notification on the left and the item list on the right) which
# Tesseract merged into a single line. Splitting on it keeps each column's
# text independent, instead of losing the second column to the line pattern's
# leading-prefix match on the first.
_COLUMN_GAP_THRESHOLD = 60


def _strip_diacritics(text: str) -> str:
    """
    Replace accented letters with their plain-ASCII base (e.g. "é" -> "e").

    Tesseract occasionally renders a spurious diacritic onto an ASCII letter
    of the game's font (e.g. "Abecean" reads as "Abecén"). `_LINE_PATTERN`'s
    name group only allows `[A-Za-z]`, so an unstripped diacritic truncates
    the match right before it - severing the name from the "(amount)" that
    follows and silently falling back to an amount of 1.

    Parameters
    ----------
    text : str
        Raw OCR'd text, possibly containing accented characters.

    Returns
    -------
    str
        The same text with diacritics removed.
    """
    return "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    )


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


def match_ocr_data(
    data: pytesseract.TesseractDataDict,
    known_names: list[str],
    known_effect_names: frozenset[str] = frozenset(),
) -> list[InventoryIngredient]:
    """
    Fuzzy-match Tesseract OCR output against known ingredient names.

    Pure post-processing, independent of where the OCR itself ran - shared by
    `extract_ingredients_from_image` (local, in-process Tesseract, used by the
    CLI) and the API's upload path (Tesseract runs in the isolated `ocr`
    service; this function is called on the `TesseractDataDict` it returns).

    Parameters
    ----------
    data : pytesseract.TesseractDataDict
        Output of `pytesseract.image_to_data(..., output_type=Output.DICT)`.
    known_names : list[str]
        Whitelist of valid ingredient names to match OCR text against.
    known_effect_names : frozenset[str], optional
        Lowercased magic effect names (e.g. "resist frost"), used to reject
        the selected item's tooltip - its four effect labels have no
        ingredient name namespace overlap (verified: Skyrim has zero
        ingredients sharing a name with an effect) but can still fuzzy-match
        one by coincidence (e.g. "Resist Frost" scores 85 against the real
        ingredient "Farengar's Frost Salt", above `_FUZZY_SCORE_CUTOFF`).
        Effect labels never carry a trailing "(amount)", so only checked
        when `amount_candidate` is absent - a real owned-1 ingredient row
        also lacks the suffix, and this must not reject those. Empty by
        default so callers that can't supply it (yet) keep prior behavior.

    Returns
    -------
    list[InventoryIngredient]
        Ingredients recognized with high enough confidence.
    """
    ingredients: list[InventoryIngredient] = []

    for segment in _line_segments(data):
        segment = _strip_diacritics(segment.strip())
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

        if name_candidate.lower() in _UI_CHROME_NAMES:
            continue

        if amount_candidate is None and name_candidate.lower() in known_effect_names:
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
            amount=_parse_amount(amount_candidate) if amount_candidate is not None else 1,
        ))

    return ingredients


def _parse_amount(amount_text: str) -> int:
    """
    Parse an OCR'd amount string into an int, correcting a known digit misread.

    Parameters
    ----------
    amount_text : str
        The matched amount text - digits, with a possible leading '}' in
        place of a misread "1" (see `_LINE_PATTERN`).

    Returns
    -------
    int
        The parsed amount.
    """
    return int(amount_text.replace("}", "1"))


def merge_ocr_matches(
    primary: list[InventoryIngredient],
    supplementary: list[InventoryIngredient],
) -> list[InventoryIngredient]:
    """
    Merge two OCR passes' matches, additively.

    `primary` always wins, except for its own default-amount fallback.
    Every ingredient `primary` (the binarized pass) already recognized with
    an explicit amount is kept exactly as-is, untouched. Names present in
    `supplementary` (the plain, non-binarized pass) but absent from
    `primary` are added - this recovers a word that binarization corrupted
    (e.g. "Troll" -> "Teal", dropping "Troll Fat" below the fuzzy-match
    cutoff).

    A `primary` entry whose amount is exactly 1 is ambiguous: the game
    itself never prints a "(1)" suffix for a single-owned item, so `amount
    == 1` is indistinguishable from `_LINE_PATTERN` simply failing to find
    the amount group at all (e.g. binarization thinning the bracket text
    away, as happened for "Dragon's Tongue (9)" - the binarized pass read
    only the name and silently defaulted to 1). If `supplementary` matched
    the same name with an amount other than 1, that number can only have
    come from an actual parsed "(amount)" group (1 is always the fallback,
    never a genuine parse result other than a real single-owned item), so
    it is trusted over `primary`'s default. A real single-owned item has no
    bracket in the source image for either pass to find, so this can never
    override a correct amount of 1 with a wrong one.

    Parameters
    ----------
    primary : list[InventoryIngredient]
        Matches from the binarized pass - authoritative except for its own
        default-to-1 fallback.
    supplementary : list[InventoryIngredient]
        Matches from the plain (autocontrast-only) pass - fills in names
        `primary` missed entirely, and corrects `primary` amounts that
        fell back to the default.

    Returns
    -------
    list[InventoryIngredient]
        `primary`'s entries (amount corrected from `supplementary` where
        `primary` defaulted to 1), plus any `supplementary` entry whose
        name isn't already among them.
    """
    primary_names = {ingredient.name for ingredient in primary}
    supplementary_by_name = {ingredient.name: ingredient for ingredient in supplementary}

    corrected_primary = [
        supplementary_by_name[ingredient.name]
        if ingredient.amount == 1
        and ingredient.name in supplementary_by_name
        and supplementary_by_name[ingredient.name].amount != 1
        else ingredient
        for ingredient in primary
    ]

    return corrected_primary + [
        ingredient for ingredient in supplementary if ingredient.name not in primary_names
    ]


def extract_ingredients_from_image(
    image_bytes: bytes,
    filename: str,
    known_names: list[str],
    known_effect_names: frozenset[str] = frozenset(),
) -> list[InventoryIngredient]:
    """
    Run OCR on a screenshot and fuzzy-match recognized lines against known ingredient names.

    Used by the CLI's `Inventory.retrieve()`. Dispatches to the `ocr`
    container when reachable, else a local Tesseract install - see
    `app.ocr_client.run_ocr`. The API's upload path does not call this: it
    calls `run_remote_ocr` directly and never falls back, since it
    deliberately never runs Tesseract in-process (but applies the same
    two-pass merge itself - see `app/api.py`).

    Parameters
    ----------
    image_bytes : bytes
        Raw screenshot image bytes (PNG).
    filename : str
        Original filename, forwarded to the OCR service if that backend is used.
    known_names : list[str]
        Whitelist of valid ingredient names to match OCR text against.
    known_effect_names : frozenset[str], optional
        Lowercased magic effect names, forwarded to `match_ocr_data` to
        reject the selected item's tooltip effect labels - see its
        docstring.

    Returns
    -------
    list[InventoryIngredient]
        Ingredients recognized with high enough confidence.

    Raises
    ------
    OcrUnavailableError
        If neither the `ocr` container nor a local Tesseract install is usable.
    """
    result = run_ocr(image_bytes, filename)

    primary = match_ocr_data(result["binarized"], known_names, known_effect_names)
    supplementary = match_ocr_data(result["plain"], known_names, known_effect_names)

    return merge_ocr_matches(primary, supplementary)
