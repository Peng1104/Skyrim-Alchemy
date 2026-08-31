"""Scrape the alchemy effects data from the UESP Skyrim page."""

from typing import cast as type_cast

from bs4 import BeautifulSoup, Tag

from app.models import Effect
from app.scraping._effect_priorities import get_effect_priority_overrides
from app.scraping._http_cache import download_data


def get_effect(row: Tag) -> Effect:
    """
    Retrieve the effect data from a table row.

    Parameters
    ----------
    row : Tag
        The BeautifulSoup Tag object representing the table row.

    Returns
    -------
    Effect
        An Effect object containing the effect data.
    """
    cells = row.find_all(['th', 'td'])

    effect_name_tag = cells[0].find('a')
    effect_classes = type_cast('list[str] | None', cells[0].get('class')) or []

    return Effect(
        name=type_cast(Tag, effect_name_tag).get_text(strip=True),
        cost=float(cells[3].get_text(strip=True)),
        magnitude=float(cells[4].get_text(strip=True)),
        duration=float(cells[5].get_text(strip=True)),
        harmful='EffectNeg' in effect_classes,
    )


def process_table(table: Tag) -> dict[str, Effect]:
    """
    Process a table of effects and return a dictionary mapping effect names to Effect objects.

    Parameters
    ----------
    table : Tag
        The BeautifulSoup Tag object representing the table.

    Returns
    -------
    dict[str, Effect]
        A dictionary mapping effect names to Effect objects.
    """
    effects_data: dict[str, Effect] = {}

    for row in table.find_all('tr')[1:]:
        effect = get_effect(row)

        effects_data[effect.name] = effect

    return effects_data


def get_effects_data() -> dict[str, Effect]:
    """
    Scrape the Skyrim Alchemy Effects page from UESP.net.

    Returns
    -------
    dict[str, Effect]
        Dictionary mapping effect names to their base cost, magnitude, and duration.
    """
    soup = BeautifulSoup(download_data(
        "https://en.uesp.net/wiki/Skyrim:Alchemy_Effects"), 'lxml')

    data: dict[str, Effect] = {}

    for table in soup.find_all('table', class_='wikitable sortable'):
        data.update(process_table(table))

    for effect in data.values():
        effect.priority_overrides = get_effect_priority_overrides(
            effect.name, effect.magnitude, effect.duration
        )

    return data
