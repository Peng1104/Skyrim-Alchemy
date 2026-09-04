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

As of this writing, the page's 3 tables list **190 ingredients** in total.
This isn't hardcoded anywhere in the project — it's whatever UESP's page
happens to contain the next time the cache is refreshed — but it's the
practical upper bound on how many distinct ingredient types the optimizer
could ever see, which matters for its worst-case combination count (see
[section 6.1 of the calculation doc](../calculation/CALCULATION.en.md#61-combination-count)).

### 1.1 DLC and Creation Club coverage

The scraper does **not** filter by origin — it captures every row in the
page's tables unconditionally, whether the ingredient is from the base
game, an official DLC (Dawnguard, Hearthfire, Dragonborn), or any
Creation Club/Anniversary Edition content (Rare Curios, Fishing, Saints &
Seducers, The Cause, Plague of the Dead, etc.). None of that is filtered
out, and there's no setting to exclude it — if it's a row on UESP's
`Skyrim:Ingredients` page, it ends up in `ingredients_data`.

This also means the resulting data isn't cleanly separable by origin:
UESP tags a few rows with a small superscript badge linking to the source
DLC/Creation (`DG`, `HF`, `DB`, or a generic `CC`), but many
Creation-Club-origin ingredients (Mort Flesh from Plague of the Dead, for
example) carry no badge at all and are visually indistinguishable from
base-game ones in the table. So there's no reliable way to derive "is this
ingredient from a DLC I own" from the scraped data.

In practice this is harmless: if you don't own a given DLC/Creation, its
ingredients simply never show up in your in-game inventory, so OCR never
matches them — they just sit unused in `ingredients_data`.

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
