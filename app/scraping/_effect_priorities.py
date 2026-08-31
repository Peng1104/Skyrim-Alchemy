"""
Scrape per-effect ingredient priority tables from UESP's individual effect pages.

Some effects (Damage Health being the most notable) have ingredients with
non-standard magnitude/duration for that specific effect. When a potion
combines two such ingredients, the game does not merge their modifiers - it
uses only the single highest-priority ingredient's values, discarding the
rest entirely. Each effect's own wiki page (e.g. `Skyrim:Damage_Health`) lists
this in an "Ingredient / Priority / Base Mag / Base Dur / Mag Mult / Gold Mult"
table; most effects have no such table (all of their ingredients are standard).
"""
import re
from typing import cast as type_cast

from bs4 import BeautifulSoup, Tag

from app.scraping._http_cache import download_data

_VALUE_PATTERN = re.compile(r'[\d.]+')


def _parse_numeric(text: str) -> float | None:
    """
    Parse a leading numeric value out of a table cell's text, ignoring footnote markers.

    Parameters
    ----------
    text : str
        Cell text, possibly with a trailing footnote symbol (e.g. "0†").

    Returns
    -------
    float | None
        The parsed number, or None if no number is present.
    """
    match = _VALUE_PATTERN.match(text.strip())
    return float(match.group()) if match else None


def _find_priority_table(soup: BeautifulSoup) -> Tag | None:
    """
    Find the ingredient priority table on an effect page, if present.

    Parameters
    ----------
    soup : BeautifulSoup
        Parsed effect page.

    Returns
    -------
    Tag | None
        The priority table, or None if this effect has no non-standard ingredients.
    """
    for table in soup.find_all('table', class_='wikitable sortable'):
        header_cells = [
            cell.get_text(strip=True) for cell in type_cast(Tag, table.find('tr')).find_all(
                ['th', 'td'])
        ]
        if 'Priority' in header_cells and 'Base Mag' in header_cells and 'Base Dur' in header_cells:
            return table

    return None


def get_effect_priority_overrides(
    effect_name: str, standard_magnitude: float, standard_duration: float
) -> dict[str, tuple[float, float]]:
    """
    Scrape the ingredient priority overrides for a single effect, if it has any.

    Parameters
    ----------
    effect_name : str
        The effect's name (e.g. "Damage Health").
    standard_magnitude : float
        The effect's standard base magnitude, used as the ratio denominator.
    standard_duration : float
        The effect's standard base duration, used as the ratio denominator.

    Returns
    -------
    dict[str, tuple[float, float]]
        Maps ingredient name to (magnitude_ratio, duration_ratio) for every
        ingredient with a non-blank Priority on this effect's page. Empty if
        the effect has no non-standard ingredients or no dedicated page.
    """
    url = "https://en.uesp.net/wiki/Skyrim:" + effect_name.replace(' ', '_')

    try:
        soup = BeautifulSoup(download_data(url), 'lxml')
    except Exception as fetch_error:
        print(f"WARNING: could not fetch priority table for '{effect_name}': {fetch_error}")
        return {}

    table = _find_priority_table(soup)

    if table is None:
        return {}

    overrides: dict[str, tuple[float, float]] = {}

    for row in table.find_all('tr')[1:]:
        cells = row.find_all(['th', 'td'])

        if len(cells) < 4 or not cells[1].get_text(strip=True):
            continue  # blank Priority - standard ingredient, no override needed

        name_tag = cells[0].find('a')
        if name_tag is None:
            continue

        name = name_tag.get_text(strip=True)
        base_mag = _parse_numeric(cells[2].get_text(strip=True))
        base_dur = _parse_numeric(cells[3].get_text(strip=True))

        if base_mag is None or base_dur is None:
            continue

        magnitude_ratio = base_mag / standard_magnitude if standard_magnitude else 1.0
        duration_ratio = base_dur / standard_duration if standard_duration else 1.0

        overrides[name] = (magnitude_ratio, duration_ratio)

    return overrides
