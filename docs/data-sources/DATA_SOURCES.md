# Ingredient and effect data (binary plugin reading)

This document describes where the project's ingredient and effect data
comes from: every active Skyrim plugin's own binary data, read directly.
No wiki, no scraping, no HTTP requests.

Only the command-line tool scans the game install and writes the cache.
It is the only process that has a local path to the game. The optimizer
and the API only ever read the cache. See section 3 for what happens
when that cache is missing.

## 1. Ingredients

Every ingredient in the active load order becomes part of the ingredient
database, built from its own binary record.

| Attribute | Comes from | Notes |
| :--- | :--- | :--- |
| Name | The record's display text field | Either literal text, or a localized string id resolved against the defining plugin's own packed string data, see section 1.2 |
| Effects | Up to 4 pairs of entries on the record, one per effect | Each pair is a 12-byte structure holding the effect's magnitude, an unused area value, and a duration, exactly as that ingredient produces it. There is no shared base any of this is relative to, see section 1 of the [calculation](../calculation/CALCULATION.md) document |
| Source plugin and FormID | The record's own identity after override resolution | Identifies the ingredient's authoritative, post-override record, see section 1.1 |

As of this writing, a full scan of a real modded install produces 218
ingredients. This is not hardcoded anywhere. It is whatever the active
load order actually contains, and it is the practical upper bound on how
many distinct ingredient types the optimizer could ever see, which
matters for its worst-case combination count, see section 8.1 of the
[calculation](../calculation/CALCULATION.md) document.

### 1.1 Override resolution

Skyrim's plugin format lets a later plugin in the load order redefine an
earlier plugin's record by reusing its FormID, a genuine override, not a
new item.

1. Each plugin's own ingredient and effect records are first parsed in
   isolation into a per-plugin snapshot, see the
   [Plugin Cache](../cache/plugin/PLUGIN_CACHE.md) document for why that is
   cacheable per plugin.
2. The whole load order is then walked once, vanilla masters, then
   Creation Club content, see section 1.3, then the user's own active
   plugin list, in that order, and every record is indexed by its
   canonical identity.
3. A plugin later in the load order simply overwrites the index entry
   for a FormID an earlier plugin already defined, so the index ends up
   holding only the final, authoritative version of every record,
   exactly how the game engine itself resolves overrides.

See the [game data](../game_data/GAME_DATA.md) document for the full
mechanics, including the name-collision risk that follows from it.

An ingredient or effect's recorded source plugin and FormID reflect that
authoritative version, not necessarily the plugin that originally
introduced the item. An ingredient originally added by a Creation Club
plugin, but since patched by a widely used community compatibility
patch, reports that patch as its source.

### 1.2 Localized strings and the DLC archive fallback

A record's display text field can hold either of two forms:

| Form | Where the text lives |
| :--- | :--- |
| Literal text | Directly in the record |
| Numeric localized string id | A strings file inside the defining plugin's own packed archive |

Several of Skyrim Special Edition's own official add-ons ship with no
archive of their own at all. Their strings are bundled inside the base
game's own interface archive instead, under each add-on's own file stem.
Resolving a plugin's strings falls back to the base game's own archives
whenever a plugin's own stem-matched search finds nothing, which covers
this without hardcoding any specific add-on's filename.

### 1.3 Creation Club and its own load list

Creation Club content is not listed in the user's own active plugin list
the way a regular mod is. The game engine auto-loads whatever is listed
in a separate, plain-text file in the game's own install root, one
plugin per line, not any mod-manager profile, independently of the
user's own active plugin list entirely. A popular mod manager only
lists Creation Club content as a priority-ordering entry, unrelated to
whether the plugin actually loads, so that separate file is the only
reliable source for which Creation Club content is actually active.

That separate file, and the vanilla masters list, name plugins with the
publisher's own mixed-case spelling, which does not necessarily match
the actual on-disk filename on a case-sensitive filesystem, a Steam
library shared with Windows and mounted on Linux is commonly one of
those.

| | Behavior |
| :--- | :--- |
| Naive existence check against the published spelling | Silently drops the plugin from the whole scan when the two differ, along with any of its ingredients not overridden by some other active plugin |
| Current handling | Builds a lowercased-to-actual filename map once per run, and resolves every plugin name from any of these lists through it before adding it to the load order |

This always opens files by their real, exact casing regardless of what
spelling the source list used.

### 1.4 Name-collision risk

Two unrelated records, different FormIDs, no override relationship, can
still coincidentally resolve to the same display name. This is a real,
if rare, risk inherent to keying the final database by name rather than
by FormID. See the [game data](../game_data/GAME_DATA.md) document for
the full explanation.

## 2. Effects

An effect is only ever added to the effect database when it is actually
referenced by some ingredient. The game defines many thousands of effect
records unrelated to alchemy, enchantments, quest and scripted abilities,
and so on, and including every one of them unconditionally would risk an
irrelevant record silently overwriting a real alchemy effect that
happens to share its display text, see the
[game data](../game_data/GAME_DATA.md) document's section 2.

| Attribute | Comes from |
| :--- | :--- |
| Base cost | A 32-bit float on the record |
| Harmful | Whether the record's harmful flag bits are set, a rule that matches 205 known effects with zero mismatches |

The cost value, and every other float read from a plugin, including each
ingredient's own magnitude and duration, is stored exactly as the game's
own binary value decodes to, deliberately not rounded. A value like
`0.30000001192092896` for a cost a wiki itself documents as `0.3` is not
corruption. `0.3` has no exact binary floating-point representation, so
the game's own binary bytes decode to that same nearest-representable
value. The goal is to keep exactly the value the plugin itself stores,
not a prettier, rounded approximation of it.

There is no magnitude or duration field on an effect record at all. See
section 2.1 of the [calculation](../calculation/CALCULATION.md) document
for how cost and the harmful flag combine with each ingredient's own
magnitude and duration.

## 3. Caching

The scan writes three kinds of files under a dedicated cache directory:

| Files | Contents | Document |
| :--- | :--- | :--- |
| One small file per plugin | That plugin's own raw scan results | [Plugin Cache](../cache/plugin/PLUGIN_CACHE.md) |
| `ingredients.json` | The merged, override-resolved ingredient database | [Ingredient Cache](../cache/ingredients/INGREDIENTS_CACHE.md) |
| `effects.json` | The merged, override-resolved effect database | [Effect Cache](../cache/effects/EFFECTS_CACHE.md) |

Scanning is incremental per plugin, not all or nothing. A plugin whose
own bytes have not changed since the last scan reuses its cached data
verbatim, and only plugins that actually changed get reprocessed. This
matters in practice, on a real install with around 100 active plugins:

| Scan | Time |
| :--- | :--- |
| Full, every plugin reprocessed | Around 30 seconds |
| Rescan after touching a single plugin | Around 0.2 seconds |

A roughly 150x difference, for exactly the common case of adding,
updating, or removing one or two mods at a time.

Only the command-line tool ever triggers a scan. If the cache has not
been populated yet, populate it first by running that tool with its
refresh option against a local Skyrim install:

```bash
uv run python cli.py --refresh
```

To pick up changes after installing, removing, or reordering plugins,
re-run with that same option. There is no separate cache-clearing
command. An unchanged plugin is never reprocessed, so a refresh is cheap
even with many plugins installed. The refresh option's actual effect is
to ignore every cached snapshot and reprocess every plugin from scratch,
useful if the cache itself is ever suspected of being stale or
corrupted, though a single malformed plugin's cached file is already
handled gracefully on its own without needing a full refresh.
