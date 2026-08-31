"""Scrape ingredients data from the UESP Skyrim page."""

import re
from typing import cast as type_cast

from bs4 import BeautifulSoup, Tag

from app.models import Ingredient, IngredientEffect, Modifier
from app.scraping._http_cache import download_data


def get_modifiers(effect_cell: Tag) -> dict[Modifier, float] | None:
    """
    Retrieve if an effect cell contains modifiers.

    Parameters
    ----------
    effect_cell : Tag
        The Tag containing the effect cell.

    Returns
    -------
    dict[Modifier, float] | None
        A dictionary of modifiers with their factors, or None if no modifiers are found.
    """
    modifiers: dict[Modifier, float] = {}

    for data in effect_cell.find_all('a', title=[mod.value for mod in Modifier]):
        modifier = Modifier(str(data['title']))
        factor = data.find_previous('span')

        if factor:
            factor_value = factor.find('b')

            if factor_value:
                modifiers[modifier] = float(factor_value.get_text(strip=True))

    if not modifiers:
        return None

    return modifiers


def get_effect(cell: Tag) -> IngredientEffect:
    """
    Extract an ingredient effect from an effect cell.

    Parameters
    ----------
    cell : Tag
        Tag containing the data cell.

    Returns
    -------
    IngredientEffect
        An object representing the ingredient effect.
    """
    name = cell.find('a', string=re.compile(r'\S+'))

    return IngredientEffect(
        name=type_cast(Tag, name).get_text(strip=True),
        modifiers=get_modifiers(cell)
    )


def get_effects(row: Tag) -> list[IngredientEffect]:
    """
    Retrieve the effects for an ingredient from its table row.

    Parameters
    ----------
    row : Tag
        Tag containing the ingredient row.

    Returns
    -------
    list[IngredientEffect]
        List of effects for the ingredient.
    """
    effect_cells = type_cast(
        Tag, row.find_next_sibling('tr')).find_all('td')

    effects_list: list[IngredientEffect] = []

    for cell in effect_cells[:4]:
        effects_list.append(get_effect(cell))

    return effects_list


def get_name(row: Tag) -> str:
    """
    Extract the ingredient name from a table row.

    Parameters
    ----------
    row : Tag
        Tag containing an ingredient row.

    Returns
    -------
    str
        The ingredient name.
    """
    cells = row.find_all('td')
    name = cells[1].find('a')

    return type_cast(Tag, name).get_text(strip=True)


def process_table(table: Tag) -> dict[str, Ingredient]:
    """
    Process a table and extract all the ingredients data.

    Parameters
    ----------
    table : Tag
        Tag containing the table.

    Returns
    -------
    dict[str, Ingredient]
        Dictionary mapping ingredient names to their effects.
    """
    data: dict[str, Ingredient] = {}

    for row in table.find_all('tr', id=True):
        name = get_name(row)

        data[name] = Ingredient(
            name=name,
            effects=get_effects(row)
        )

    return data


def get_ingredients_data() -> dict[str, Ingredient]:
    """
    Scrape the Skyrim ingredients page from UESP.net.

    Returns
    -------
    dict[str, Ingredient]
        Dictionary mapping ingredient names to their effects.
    """
    soup = BeautifulSoup(download_data(
        "https://en.uesp.net/wiki/Skyrim:Ingredients"), 'lxml')

    data: dict[str, Ingredient] = {}

    for table in soup.find_all('table', class_='wikitable striped2_1'):
        data.update(process_table(table))

    return data
