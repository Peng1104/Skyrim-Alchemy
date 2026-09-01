# Ingredient and effect data (UESP scraping)

This document describes where the project's ingredient and effect data comes
from, and how it's scraped and cached. The reference implementation lives in
`app/scraping/` (`_ingredients.py`, `_effects.py`, `_effect_priorities.py`,
`_http_cache.py`).

There are two datasets, both scraped from [UESP](https://en.uesp.net/) (the
Unofficial Elder Scrolls Pages) and both loaded once per `AlchemyOptimizer`
instance (`app/optimizer/_engine.py`) via `get_ingredients_data()` and
`get_effects_data()` (`app/scraping/__init__.py`).

## 1. Ingredients

Source: [Skyrim:Ingredients](https://en.uesp.net/wiki/Skyrim:Ingredients).

`app/scraping/_ingredients.py` parses every `table.wikitable.striped2_1` on
the page with BeautifulSoup. Each ingredient occupies **two consecutive table
rows**:

- The first row (matched by having an `id` attribute) holds the ingredient's
  name, taken from the second cell's link text.
- The row right after it holds up to 4 cells, one per effect the ingredient
  can produce. Each cell's link text is the effect name; if the cell also
  shows a `Value`/`Magnitude`/`Duration` modifier icon (a non-standard
  multiplier for that specific ingredient/effect pairing), the icon's
  preceding `<b>` value is captured as that modifier's factor
  (`get_modifiers`).

This produces a `dict[str, Ingredient]` — each `Ingredient` has a name and a
list of up to 4 `IngredientEffect`s, each with an optional
`{Modifier: factor}` map.

## 2. Effects

Source: [Skyrim:Alchemy Effects](https://en.uesp.net/wiki/Skyrim:Alchemy_Effects).

`app/scraping/_effects.py` parses every `table.wikitable.sortable` on the
page. For each row it reads the effect's name, base `cost`, base
`magnitude`, and base `duration` from fixed column positions, and derives
`harmful` from the row's CSS class: UESP marks harmful (poison-type) effect
rows with `EffectNeg`, beneficial ones with `EffectPos`.

### 2.1 Per-effect priority overrides

A handful of effects (*Damage Health* being the most notable) have
ingredients with a non-standard magnitude/duration specifically for that
effect — see
[section 2 of the calculation doc](../calculation/CALCULATION.en.md#2-resolving-priority-between-ingredients)
for why that matters. `app/scraping/_effect_priorities.py` fetches each
effect's own wiki page
(`https://en.uesp.net/wiki/Skyrim:<Effect_Name_With_Underscores>`) and looks
for a table with `Priority`/`Base Mag`/`Base Dur` columns. When present,
every ingredient with a non-blank `Priority` gets an entry in
`Effect.priority_overrides`, mapping its name to
`(magnitude_ratio, duration_ratio)` — its base magnitude/duration divided by
the effect's standard ones. Most effects have no such table, and end up with
no overrides at all.

This runs once per effect after the main effects table is parsed, so loading
effects data costs one page fetch for the effects table plus one fetch per
effect (all cached — see below).

## 3. Caching

`app/scraping/_http_cache.py`'s `download_data()` wraps every fetch: on the
first request for a URL, it downloads the page and writes the raw HTML to
`cache/pages/<path-after-the-domain>.html` (e.g. `Ingredients.html`,
`Alchemy_Effects.html`, `Damage_Health.html`); every subsequent call for the
same URL reads straight from that file, no network request involved. There
is no freshness check or expiry — once cached, a page is never re-downloaded
on its own.

To pick up changes made on UESP, delete the cache and let the next run
re-fetch everything:

```bash
rm -rf cache/pages/            # CLI - forces a fresh scrape on the next run
```

```bash
curl -X DELETE http://localhost:8001/cache/pages   # API - same effect
```

Both remove every cached page indiscriminately (ingredients, the effects
table, and every per-effect priority page) — there's no way to invalidate
just one.
