🌐 [English](EFFECTS_CACHE.md) · [Português](EFFECTS_CACHE.pt.md) · [Deutsch](EFFECTS_CACHE.de.md)

# Effect Cache

This document describes the on-disk cache holding the final magic effect
database, at `cache/game_data/effects.json`, built in the same pass as
the [Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md) and always written alongside
it. It is not a full dump of every magic effect that exists in every
active plugin. The game defines many thousands of effects that have
nothing to do with alchemy: spells, enchantments, quest-only abilities,
and so on. An entry only ends up here if at least one ingredient in the
[Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md) actually produces it. Section 3
explains why that filtering matters.

## 1. Structure

A JSON object mapping each effect's display name to its data.

```jsonc
{
  "Restore Stamina": {
    "name": "Restore Stamina",
    "cost": 0.6000000238418579,
    "harmful": false,
    "source_file": "unofficial skyrim special edition patch.esp",
    "form_id": "0003EB16"
  }
  // one entry per effect actually produced by some ingredient
}
```

(Real excerpt.)

| Field | Read from | Meaning |
| :--- | :--- | :--- |
| `name` | `FULL` subrecord | The effect's display name, also the key it is stored under. Two genuinely unrelated effects, no override relationship between them, could in principle share the exact same display text and collide here, with one silently overwriting the other. This is rare, but not hypothetical: see section 3 for a real case. |
| `cost` | `DATA` subrecord, bytes 4-7 (32-bit float) | The effect's own base cost, a real property of the effect, independent of any particular ingredient, used when working out how much a potion using this effect is worth. Kept exactly as those 4 bytes decode to, with no rounding. See section 2 for why it looks like `0.6000000238418579` instead of a cleaner `0.6`. |
| `harmful` | `DATA` subrecord, bytes 0-3 (32-bit flags), bit `0x01` (Hostile) or `0x04` (Detrimental) | Whether the game classifies this as a harmful, poison-type effect. True if either bit is set. See section 2 for why this specific bit combination. |
| `source_file` | Which plugin's magic effect record won the override resolution | Which plugin's version of this effect is the one actually in effect, using the same override rule as an ingredient's `source_file`: not necessarily whoever first added the effect, but whoever's version currently wins. Informational only. |
| `form_id` | That winning record's own FormID, unmodified | That winning plugin's own identifier for the effect. Informational only. |

There is deliberately no magnitude or duration field here, and there
never will be. Those describe how strongly one particular ingredient
produces this effect, and that varies ingredient by ingredient, as
described in the [Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md) document's
`effects` list. No shared base magnitude or duration per effect exists
anywhere in the game's own data.

## 2. Where cost and harmful actually come from

Neither of these is something this project decides or computes. Both are
read as they are from bytes Bethesda's own plugin format already
defines, inside every magic effect record's `DATA` block: a 32-bit flags
field at byte offset 0, and a 32-bit float base cost at byte offset 4.

`harmful` is derived from two individual bits of that flags value: bit
`0x01` (Hostile) and bit `0x04` (Detrimental). It is true if either bit
is set. This specific rule, Hostile or Detrimental rather than just
Detrimental alone, was chosen by checking it against every one of the
205 alchemy effects a wiki independently documents as harmful or
beneficial. Detrimental alone disagreed with that reference on 2 of
them, Paralysis and Fear, which the game itself flags Hostile but not
Detrimental, while Hostile or Detrimental matched all 205 with zero
mismatches. Both bit positions, and the byte offsets above, come from
Bethesda's own record layout, not from anything this project invented.

Every other float this project reads from a plugin, this `cost`
included, and every ingredient's own magnitude and duration, is kept
exactly as that 4-byte float decodes to, with no rounding applied. That
is why a value like `0.6000000238418579` shows up instead of a cleaner
`0.6`. It is not corruption: it is what those 4 bytes actually decode
to, since `0.6` has no exact binary floating-point representation, so
the game's own data never stored a perfectly clean `0.6` to begin with.
Converting it to a wider float for serialization just makes that
pre-existing imprecision visible instead of hiding it behind a rounded
display value.

## 3. How it is populated

Built in the same step that builds the
[Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md). While resolving each
ingredient's effects by name, matching each ingredient's pointer against
the effect it actually refers to, every effect that gets successfully
matched this way is also recorded here. This file ends up containing
exactly the effects actually reachable from at least one ingredient, and
nothing else.

This filtering is deliberate, not incidental. Including every magic
effect a plugin defines, unconditionally, would also pull in effects
completely unrelated to alchemy, some of which can coincidentally share
display text with a real alchemy effect. This has happened in practice:
a quest-only effect from a DLC once resolved to the exact same name as a
genuine alchemy effect, but with a different cost, which would have
silently corrupted that alchemy effect's data if every effect were
included unconditionally. Restricting this file to only what ingredients
actually use avoids that specific class of collision, though the
narrower case from section 1, two effects that are both actually used by
some ingredient still sharing a name, remains possible.

This file and the [Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md) are always
written together, in the same pass. See that document's section 3.1 for
exactly when a rewrite happens versus when a previous scan's result is
reused as is.

## 4. Who reads it

Loaded together with the [Ingredient Cache](../ingredients/INGREDIENTS_CACHE.md) at
startup, but treated more leniently if missing. An absent ingredient
database is a hard failure, since nothing in the application can
function without one, while an absent effect database is simply treated
as no effects known yet, and the application keeps starting. In practice
the two files are always written together, so this mostly matters for a
partially set up or manually altered cache folder, not for normal use.
