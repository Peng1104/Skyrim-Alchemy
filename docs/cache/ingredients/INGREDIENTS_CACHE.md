🌐 [English](INGREDIENTS_CACHE.md) · [Português](INGREDIENTS_CACHE.pt.md) · [Deutsch](INGREDIENTS_CACHE.de.md)

# Ingredient Cache

This document describes the on-disk cache holding the complete, final
ingredient database, at `cache/game_data/ingredients.json`: every
ingredient from every active plugin, already resolved into the one
version that actually counts (section 2 explains what "resolved" means
here). This is the file the rest of the application reads. The optimizer,
the API, everything downstream of the game-data scan goes through this
file, never through the raw per-plugin data it is built from (see the
[Plugin Cache](../plugin/PLUGIN_CACHE.md) document).

As of this writing, a full scan of a real modded install produces 218
ingredients, not a fixed number, just whatever the active plugins happen
to contain.

## 1. Structure

A JSON object mapping each ingredient's display name to its data.

```jsonc
{
  "Silverside Perch": {
    "name": "Silverside Perch",
    "effects": [
      {
        "name": "Restore Stamina",
        "magnitude": 5.0,
        "duration": 0.0
      },
      {
        "name": "Damage Stamina Regen",
        "magnitude": 100.0,
        "duration": 5.0
      }
      // up to 4 effects total
    ],
    "source_file": "Skyrim.esm",
    "form_id": "00106E1C"
  }
  // one entry per ingredient
}
```

(Real excerpt, truncated.)

| Field | Meaning |
| :--- | :--- |
| `name` | The ingredient's display name, also the key it is stored under. |
| `effects` | Up to 4 effects this ingredient produces. Each one's `magnitude` and `duration` are this specific ingredient's own real strength for that effect, never rounded and never relative to any shared baseline: no such baseline exists in the game's own data, so two ingredients can list wildly different numbers for what looks like the same effect. The `name` here is the effect's resolved display name, already cross-referenced against whichever plugin defines that effect. |
| `source_file` | Which plugin's version of this ingredient is the one actually in effect, not necessarily the plugin that originally introduced it. If a later mod, or a compatibility patch, overrides an earlier plugin's ingredient, this names that later plugin instead. Informational only: nothing in the calculation uses this field, it exists for tracing where an ingredient's numbers come from. |
| `form_id` | That winning plugin's own identifier for the ingredient. Also informational only. |

## 2. Identity behind the scenes

This file itself does not expose the ingredient's underlying plugin
identity: it keys everything by display name instead, since that is what
the rest of the application needs to match against (an ingredient
recognized from a screenshot, for instance, is matched by its name).
Internally, before this file is built, every ingredient and effect is
tracked by a more precise identity: which plugin actually defines it,
plus a numeric id that stays stable regardless of which other plugin
happens to be referencing it (see the [Plugin Cache](../plugin/PLUGIN_CACHE.md)
document's section 2.1). That precise identity is what lets an
ingredient overridden by five different mods still resolve to exactly
one entry here, the one belonging to whichever of those mods loads last,
instead of five separate, conflicting entries.

Keying the final result by name instead of by that underlying identity
carries one real, if rare, downside. Two genuinely unrelated ingredients
or effects, with no override relationship between them, could in
principle share the exact same display text and collide here, with one
silently overwriting the other. This is not a hypothetical: it has been
observed in practice, always with an effect defined for something
entirely unrelated to alchemy, a quest script for example, that happened
to reuse a name already used by a real alchemy effect.

## 3. How it is populated

Built once every active plugin's own per-plugin data is available,
freshly scanned or reused from before. Two things happen, purely by
combining data already on disk. No plugin file is reopened at this
stage.

First, a winner is picked for every ingredient and effect. Plugins are
walked in load order, and whenever two plugins define or override the
same ingredient or effect, the one that loads later wins, exactly like
the game itself resolves such conflicts. What is left afterward is
exactly one version of every ingredient and effect, the one actually in
play.

Second, each ingredient's effects are attached by name. Each winning
ingredient still only points at its effects by identifier at this stage.
Each of those pointers is looked up against the winning effects from the
first step to fill in the effect's actual display name. A pointer that
does not resolve to any known effect, because its defining plugin was
never scanned for example, is simply dropped from that ingredient
rather than failing the whole scan.

This file and the [Effect Cache](../effects/EFFECTS_CACHE.md) are always produced
and written together, in the same pass. There is no scenario where one
gets updated without the other.

### 3.1 When it is actually rewritten

If nothing changed since the previous scan, no active plugin's own data
changed, and the active plugin list itself is the same, this step is
skipped entirely and the existing file is reused as is. Any real change
anywhere, one plugin's data changed or a mod was added or removed,
causes the whole file to be rebuilt from scratch. There is no partial
update. Unlike the per-plugin cache, this file does not track which
individual ingredients changed: it is always regenerated in full from
whatever the current, complete picture is.

## 4. Who reads it

This is the database the rest of the application actually uses, loaded
once when the optimizer starts up. It is a pure read: nothing that
consumes this file ever triggers a scan itself, so it works fine even in
a place with no access to the actual game install. If this file does not
exist yet at all, that is treated as a hard error, since nothing in the
application can function without an ingredient database, so startup
fails loudly instead of quietly running with an empty one. The companion
[Effect Cache](../effects/EFFECTS_CACHE.md) is treated more forgivingly if it is
the one missing; see that document for why.
