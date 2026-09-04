# Game-data scan: override resolution and name-collision risk

This document describes how `app/game_data/` resolves overrides between
plugins, and a specific, known limitation that follows from it: two
**unrelated** records that happen to resolve to the same display name are
not both kept — the dictionaries this project builds are keyed by name, so
one of them is silently dropped. The reference implementation is
`app/game_data/_scan.py` (`_scan_plugin`, `_merge_snapshots`).

## 1. How overrides are resolved

Scanning happens in two stages (see
[DATA_SOURCES.md §3.1](../data-sources/DATA_SOURCES.md#31-incremental-scanning)
for the full incremental-caching picture). `_scan_plugin` parses one
plugin's own `INGR`/`MGEF` records in isolation, computing each record's
canonical identity `(owner_file, local_id)` via `resolve_form_id`
(`app/game_data/_plugin_records.py`), applied against that plugin's own
master list — this step never looks at any other plugin, which is what
makes its result (a `PluginGameDataSnapshot`) safe to cache per plugin.

`_merge_snapshots(load_order, snapshots)` then walks the full active load
order **once** — vanilla masters, then `Skyrim.ccc`-listed Creation Club
content, then `Plugins.txt`'s active plugins, in that exact order (see
[DATA_SOURCES.md §1.3](../data-sources/DATA_SOURCES.md#13-creation-club-and-skyrimccc))
— and indexes every record of a type by that same canonical identity. When
a later plugin in the load order defines a record with the same canonical
identity as one an earlier plugin already indexed (a genuine override —
the later plugin lists the earlier one as a master and reuses its FormID),
the later entry **replaces** the earlier one in the index. By the time the
whole load order has been walked, every key in the index holds only its
final, authoritative version — exactly how the game engine itself resolves
overrides, and exactly why `Ingredient`/`Effect.source_file` reports the
plugin that currently *wins* for that FormID, not necessarily the one that
originally introduced it (see
[DATA_SOURCES.md §1.1](../data-sources/DATA_SOURCES.md#11-override-resolution)).

This part is FormID-accurate: it is not possible for a genuine override to
be mistaken for an unrelated new record, or vice versa, because the
canonical identity is derived from the actual master-list-relative FormID
math the game itself uses — and it stays accurate however many plugins
were reused from cache vs. freshly parsed in `_scan_plugin`, since a cached
snapshot's own canonical identities were computed the exact same way the
last time that plugin's bytes were actually read.

## 2. Where FormID accuracy stops: the final dictionaries are keyed by name

The second half of `_merge_snapshots` turns the FormID-keyed index into the
`dict[str, Ingredient]`/`dict[str, Effect]` the rest of the project uses,
keyed by each record's **resolved display name** — this is where FormID
accuracy no longer applies. If two records with genuinely different,
unrelated canonical identities (no override relationship between them at
all) happen to resolve to the identical display string, only one of them
survives in the final dictionary; Python's own `dict` assignment silently
overwrites the other. Iteration order over the index follows insertion
order during the merge (load-order position, master-file-batched), so in
practice **whichever record is processed last during that pass wins** —
not necessarily the one that is semantically "correct" or most recently
overridden; it's purely a name collision, independent of the override
mechanism in section 1.

## 3. A real case hit during development

Effects are the case this project actually observed, not a hypothetical.
Early on, `effects` was built from **every** `MGEF` in the index
unconditionally (mirroring how `ingredients` is built from every `INGR`).
That produced 1525 effects — far more than alchemy has — and a spot-check
of "Damage Health" showed `cost=5.0, source_file='Dragonborn.esm'` instead
of the correct `cost=3.0, source_file='Skyrim.esm'`. The cause:
`Dragonborn.esm` defines a genuinely unrelated, quest-only `MGEF`
(`DLC2TTR4aAbDamageHealth`, used by a scripted quest ability, nothing to do
with alchemy) whose `FULL` text *also* happens to resolve to "Damage
Health" — same string, completely different FormID, no override
relationship. Because `Dragonborn.esm` is processed after `Skyrim.esm` in
load order, its unrelated `MGEF` silently overwrote the real alchemy
effect's entry.

The fix was **not** a name-collision detector — it was narrowing what
becomes an `Effect` in the first place: `_merge_snapshots`
only adds a `MGEF` to the `effects` dict when some ingredient's `EFID`
actually references it, which excludes the vast majority of `MGEF` records
(enchantments, quest abilities, etc.) before they ever reach the name-keyed
dictionary at all. This dropped the effect count from 1525 to 63 and fixed
the Damage Health case. It does **not** eliminate the general risk from
section 2 — it only removes the specific, large source of false positives
that came from including irrelevant `MGEF` records. Two *different*
ingredient-referenced effects (or two different ingredients) that
coincidentally share a name are still possible, just much rarer.

## 4. Current mitigation: none automatic — cross-reference `form_id` manually

There is no code that detects "two different, unrelated FormIDs resolved to
the same name" and flags it — a dropped duplicate is silent, same as before
this refactor. Because `Ingredient`/`Effect` now carry `source_file` and
`form_id` (see
[DATA_SOURCES.md §1](../data-sources/DATA_SOURCES.md#1-ingredients)), the
practical way to investigate a suspected collision changed: look up the
entry's `form_id` in `cache/game_data/ingredients.json`/`effects.json` and
cross-reference it against xEdit or the mod's own documentation — if the
FormID doesn't match what you expected for that name, a different plugin's
record won the name collision. Reordering the affected plugins in Mod
Organizer 2 (or the native `Plugins.txt`) and re-running with `--refresh`
changes which record's name wins, as a workaround — the same as before, but
now verifiable via `form_id` instead of only inferring it from missing
entries.
