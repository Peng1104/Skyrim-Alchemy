# Ingredient and effect data (binary plugin reading)

This document describes where the project's ingredient and effect data comes
from: **every active Skyrim plugin's own binary data** (`.esm`/`.esp`/`.esl`),
read directly — no wiki, no scraping, no HTTP requests. The reference
implementation lives in `app/game_data/` (`_scan.py`, `_load_order.py`,
`_plugin_records.py`, `_bsa.py`, `_strings.py`).

Only the CLI (`cli.py`) scans the game install and writes the cache — it's
the only process with a local `game_directory`. `AlchemyOptimizer`
(`app/optimizer/_engine.py`) and the API only ever read the cache
(`load_cached_game_data`, `app/game_data/__init__.py`) — see
[section 3](#3-caching) for what happens when that cache is missing.

## 0. Why not the wiki

Earlier versions of this project scraped
[UESP](https://en.uesp.net/wiki/Skyrim:Alchemy_Effects) for ingredient/effect
data, including a "base magnitude"/"base duration" per effect. Reading the
game's own binary format directly revealed that concept doesn't actually
exist: an effect (`MGEF`) only has a `cost` and a `harmful` flag as real,
game-defined properties. Magnitude and duration are not properties of the
*effect* at all — they belong to each *ingredient*, stored per-ingredient in
its `INGR` record's `EFIT` entries. UESP's "base" values are an editorial
convention (the values most "standard" ingredients happen to share), not a
field the game engine reads from anywhere — and that convention has real
gaps (e.g. effects like *Fortify Alchemy* that exist in the game but aren't
listed on UESP's effects table at all). Reading the binary sidesteps both
problems: every value comes from the exact same data the game engine itself
uses, and every effect any active ingredient actually produces is included,
whether vanilla, DLC, Creation Club, or third-party mod.

### 0.1 Confirmed case: the old `cost_factor` double-counted duration (Giant's Toe)

The pre-refactor `Effect`/`IngredientEffect` models had a `cost_factor`
(scraped from UESP's ingredient-effect "Value" modifier icon) that
multiplied straight into an effect's cost, alongside separate `magnitude`/
`duration` factors. The plan for this refactor removed `cost_factor`
outright, flagging it as an assumed risk since it had no known binary
counterpart in `EFIT`/`MGEF` and no case that needed it had come up during
development.

A real case did come up afterward, comparing the old and new systems'
output on the same real inventory: **Giant's Toe**, combined with
*Blisterwort* and *Wheat*, valued at **544.239** gold under the old
wiki-scraped system vs. **119.654** under the new `.esm`-based one — a
~4.5x difference, entirely attributable to one shared effect, *Fortify
Health*. Giant's Toe's real `EFIT` gives it `magnitude=4, duration=300` for
*Fortify Health* (`Wheat`'s own `Fortify Health` EFIT is `magnitude=4,
duration=60` — the un-modified case), which the new system reads and uses
directly. The old system had *also* scraped a `Value: 5.9` modifier icon
from UESP's ingredient table for this specific pairing and applied it as an
**extra** multiplicative `cost_factor` on top of the duration difference
already baked into `duration=300`.

That `5.9` was never an independent multiplier to begin with — it's UESP's
own prose explanation of the *consequence* of the 5x duration increase,
not a separate game mechanic:

$$
\left(\frac{300}{10}\right)^{1.1} \Big/ \left(\frac{60}{10}\right)^{1.1}
= 5^{1.1} \approx 5.874 \approx 5.9
$$

i.e. exactly the value-formula's own duration term (section 1.1 of
[docs/calculation/CALCULATION.md](../calculation/CALCULATION.md#11-effect-cost)),
raised to the same 1.1 exponent already applied to every effect. The old
scraper mistook this descriptive ratio for a standalone `Value` modifier
and multiplied it in as `cost_factor`, double-counting the same duration
increase the `duration=300` was already accounting for. The new system,
reading `duration=300` straight from `EFIT` with no `cost_factor` concept
at all, computes the correct value once.

Across the same real inventory, 88 of 89 non-mod recipes matched exactly
between the old and new systems (bit-for-bit on the final gold value); this
Giant's Toe case was the sole outlier, and it resolved in the new system's
favor — confirming the removal of `cost_factor` was a bug fix, not a
regression, at least for every case exercised so far.

## 1. Ingredients

Every ingredient in the active load order becomes an `Ingredient`, built
from its `INGR` record:

- **Name** — the record's `FULL` subrecord, resolved via `resolve_full`
  (`app/game_data/_strings.py`): either literal text, or a localized string
  ID resolved against the defining plugin's `.strings` BSA (see
  [section 1.2](#12-localized-strings-and-the-dlc-bsa-fallback)).
- **Effects** — up to 4 `IngredientEffect`s, one per `EFID`+`EFIT` pair on
  the record. `EFIT` (12 bytes) holds the effect's Magnitude (float32), Area
  (uint32, unused by this project), and Duration (uint32) **exactly as that
  ingredient produces it** — there is no shared "base" any of this is
  relative to (see [CALCULATION.md §1](../calculation/CALCULATION.md#1-effect-cost-and-an-ingredients-absolute-magnitude-duration)).
- **`source_file`/`form_id`** — the plugin filename and hex FormID of the
  ingredient's *authoritative* (post-override) record — see
  [section 1.1](#11-override-resolution).

As of this writing, a full scan of a real modded install produces **218
ingredients**. This isn't hardcoded anywhere — it's whatever the active load
order actually contains — but it's the practical upper bound on how many
distinct ingredient types the optimizer could ever see, which matters for
its worst-case combination count (see
[section 6.1 of the calculation doc](../calculation/CALCULATION.md#61-combination-count)).

### 1.1 Override resolution

Skyrim's plugin format lets a later plugin (in load order) redefine an
earlier plugin's record by reusing its FormID — a genuine override, not a
new item. Each plugin's own `INGR`/`MGEF` records are first parsed in
isolation into a per-plugin snapshot (`_scan_plugin`,
`app/game_data/_scan.py` — see [section 3.1](#31-incremental-scanning) for
why that's cacheable per plugin); `_merge_snapshots` then builds the load
order once — vanilla masters, then `Skyrim.ccc`-listed Creation Club content
(see [section 1.3](#13-creation-club-and-skyrimccc)), then `Plugins.txt`'s
active plugins, in that order — and indexes every `INGR`/`MGEF` record by its
canonical identity `(defining_file, local_id)`, resolved via
`resolve_form_id`. A plugin later in the load order simply overwrites the
index entry for a FormID an earlier plugin already defined, so the index
ends up holding only the final, authoritative version of every record —
exactly how the game engine itself resolves overrides. See
[docs/game_data/GAME_DATA.md](../game_data/GAME_DATA.md) for the full
mechanics, including the name-collision risk that follows from it.

`source_file`/`form_id` on `Ingredient`/`Effect` reflect that authoritative
version, not necessarily the plugin that originally introduced the item —
e.g. an ingredient originally added by a Creation Club plugin, but since
patched by the Unofficial Skyrim Special Edition Patch (USSEP), reports
USSEP as its `source_file`.

### 1.2 Localized strings and the DLC BSA fallback

A record's `FULL` subrecord can hold either literal text or a numeric
localized-string ID, in which case the actual text lives in a `.strings`
file inside one of the defining plugin's own BSAs
(`strings/<plugin_stem>_<language>.strings`, parsed by
`parse_strings_file`). One real gap found while validating this: Skyrim SE
ships `Dawnguard.esm`, `HearthFires.esm`, `Dragonborn.esm`, and `Update.esm`
with **no BSA of their own at all** — their strings are bundled inside
`Skyrim.esm`'s own `Skyrim - Interface.bsa` instead, under each DLC's own
stem. `_load_strings_table` (`app/game_data/_strings.py`) falls back to
`Skyrim.esm`'s BSAs whenever a plugin's own stem-matched search finds
nothing, which covers this without hardcoding any specific DLC filename.

### 1.3 Creation Club and `Skyrim.ccc`

Creation Club content is **not** listed in `Plugins.txt` the way a regular
mod is — Bethesda's engine auto-loads whatever is listed in `Skyrim.ccc` (a
plain-text file, one plugin per line, in the game's install root, not any
mod-manager profile) independently of `Plugins.txt` entirely. This was
confirmed empirically: the in-game Creations menu showed a Creation Club
pack as active even though Mod Organizer 2's `plugins.txt` had no entry for
it at all — MO2 only lists Creation Club content as a "Not managed by MO2"
mod-priority entry (a file-conflict-ordering artifact, unrelated to whether
the plugin actually loads). `_resolve_load_order`
(`app/game_data/_scan.py`) reads `Skyrim.ccc` via `parse_ccc`
(`app/game_data/_load_order.py`) and inserts every plugin it lists into the
load order, between the vanilla masters and `Plugins.txt`'s own content, so
Creation Club ingredients/effects are scanned the same as everything else.

`Skyrim.ccc` (and the vanilla masters list) name plugins with Bethesda's own
mixed-case spelling (e.g. `ccBGSSSE037-Curios.esl`), which does not
necessarily match the actual on-disk filename on a case-sensitive
filesystem — a Steam library shared with Windows and mounted on Linux is
commonly ext4, unlike NTFS's own case-insensitive default. A naive
`.exists()` check against the `.ccc` spelling silently drops the plugin from
the whole scan when the two differ; confirmed empirically on a real
install, where 74 of 75 `Skyrim.ccc` entries failed an exact-case check this
way, and any of their ingredients not overridden by some other active
plugin (so never read indirectly through another plugin's own, correctly
cased, master list) went missing from the ingredient database entirely.
`_index_data_dir_case_insensitively` (`app/game_data/_scan.py`) builds a
lowercased-name → actual-on-disk-name map once per scan, and every plugin
name from `Skyrim.ccc`/the vanilla masters list/`Plugins.txt` is resolved
through it before being added to the load order, so the rest of the scan
always opens files by their real, exact casing regardless of what spelling
the source list used.

### 1.4 Name-collision risk

Two **unrelated** records (different FormIDs, no override relationship) can
still coincidentally resolve to the same display name — this is a real, if
rare, risk inherent to keying the final dictionaries by name rather than by
FormID. See [docs/game_data/GAME_DATA.md](../game_data/GAME_DATA.md) for the
full explanation, including a real case this project hit during development
(a Dragonborn.esm quest-only effect that happened to resolve to the same
text as the real "Damage Health" alchemy effect).

## 2. Effects

An `Effect` is only ever created for a `MGEF` actually referenced by some
ingredient's `EFID` — the game defines many thousands of `MGEF` records
unrelated to alchemy (enchantments, quest/scripted abilities, etc.), and
building the effects table from *every* `MGEF` unconditionally let one such
irrelevant record silently clobber a real alchemy effect that happened to
share its display text (see
[docs/game_data/GAME_DATA.md](../game_data/GAME_DATA.md) for that specific
case). Each `Effect` reads two fields straight from `MGEF.DATA`
(`get_mgef_base_cost`/`get_mgef_harmful`, `app/game_data/_plugin_records.py`):

- **`cost`** — the Base Cost float32 at offset 4.
- **`harmful`** — whether the Hostile (`0x01`) or Detrimental (`0x04`) flag
  bit is set at offset 0. Validated against 205 UESP-documented effects with
  zero mismatches during development.

`cost` (and every other float read from a plugin, including each
ingredient's `magnitude`/`duration`) is stored exactly as the game's own
float32 decodes to — deliberately not rounded. A value like `0.30000001192092896`
for a `cost` UESP itself documents as `0.3` is not corruption: `0.3` has no
exact binary floating-point representation, so the game's own float32 bytes
decode to that same nearest-representable value; converting it to Python's
float64 to serialize as JSON just makes the underlying imprecision visible
instead of hiding it. The goal is to keep exactly the value the `.esm`
itself stores, not a prettier rounded approximation of it.

There is no `magnitude`/`duration` field on `MGEF` at all — confirmed by
reading xEdit's own record definitions
(`Core/wbDefinitionsTES5.pas`) in addition to the raw bytes. See
[CALCULATION.md §1](../calculation/CALCULATION.md#1-effect-cost-and-an-ingredients-absolute-magnitude-duration)
for how `cost`/`harmful` combine with each ingredient's own `EFIT` values.

## 3. Caching

`scan_game_data` (`app/game_data/_scan.py`) writes under `cache/game_data/`:

```
cache/game_data/
├── plugins/             One small JSON file per plugin's raw scan results (<plugin filename>.json)
├── ingredients.json    The final, merged Ingredient database
└── effects.json         The final, merged Effect database
```

### 3.1 Incremental scanning

Scanning is incremental **per plugin**, not just all-or-nothing. Each
active plugin's own `INGR`/`MGEF` records are parsed into a
`PluginGameDataSnapshot` (name, resolved display text, canonical FormIDs -
see `app.models`) that depends only on that plugin's own bytes and its own
BSA(s), never on any other plugin in the load order. That snapshot is
stored under its own cache-invalidation signature (size + mtime) in its own
file, `cache/game_data/plugins/<plugin filename>.json` - one small file per
plugin rather than one large file for all of them combined, so a plugin's
own contribution is easy to inspect on its own, and so a rescan only ever
rewrites the files for plugins that actually changed (see below). On a
later scan, a plugin whose signature still matches reuses its cached
snapshot verbatim - the actual binary/BSA parsing is skipped entirely for
it - and only plugins that actually changed get re-parsed. The (cheap,
purely in-memory) step that resolves `FormID` overrides and cross-plugin
effect-name references across the whole load order still runs on every
scan, over whatever mix of cached and freshly parsed snapshots the current
load order needs, and produces `ingredients.json`/`effects.json`.

This matters in practice: on a real install with ~100 active plugins, a
full scan (every plugin re-parsed, e.g. after installing many mods at once
or after `--refresh`'s `force=True`) took **~30 seconds**; touching a
single plugin's mtime and rescanning (every other plugin's snapshot reused
from cache, its file left untouched on disk) took **~0.2 seconds** - a
~150x difference, for exactly the common case of adding/updating/removing
one or two mods at a time.

A plugin removed from the load order since the last scan (mod uninstalled,
or `Plugins.txt`/`Skyrim.ccc` no longer lists it) has its
`cache/game_data/plugins/<filename>.json` deleted the next time snapshots
are saved, rather than lingering in the cache directory forever.

Only the CLI ever calls `scan_game_data` — it's the only process with a
local `game_directory` to read `.esm`/`.esp`/`.esl`/`.bsa` files from.

### 3.2 Reading the cache

`AlchemyOptimizer.__init__` calls `load_cached_game_data`
(`app/game_data/__init__.py`), which only ever reads
`ingredients.json`/`effects.json` — never scans, and never touches
`cache/game_data/plugins/` at all (that directory exists purely to make
`scan_game_data` itself faster; nothing outside `app/game_data/_scan.py`
reads it). If `cache/game_data/ingredients.json` doesn't exist yet,
`load_cached_game_data` raises `GameDataNotCachedError`; the API
(`app/api.py`) lets that propagate into a `RuntimeError` at import time,
so the process fails loudly at startup with a clear message instead of
serving requests with an empty database. Run the CLI with `--refresh`
against a local Skyrim install first to populate the cache:

```bash
uv run python cli.py --refresh
```

To pick up changes after installing/removing/reordering plugins, re-run
with `--refresh` — there's no separate cache-clearing endpoint or flag; per
[section 3.1](#31-incremental-scanning), an unchanged plugin is never
re-parsed, so a refresh is cheap even with many plugins installed. `force=True`
(`--refresh`'s actual effect) still re-parses every plugin from scratch and
rewrites every file under `cache/game_data/plugins/`, ignoring every cached
snapshot - use it if the cache itself is ever suspected of being stale or
corrupted, though a malformed individual plugin's cache file is already
handled gracefully on its own (treated as missing, forcing just that one
plugin to rescan without needing `--refresh` explicitly).
