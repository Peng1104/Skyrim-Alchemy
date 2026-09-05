# Game-data scan: override resolution and name-collision risk

This document describes how the game-data scan resolves overrides between
plugins, and a specific, known limitation that follows from it. Two
unrelated records that happen to resolve to the same display name are not
both kept: the final dictionaries this project builds are keyed by name,
so one of them is silently dropped.

## 1. How overrides are resolved

Scanning happens in two stages, described in full in the
[Plugin Cache](../cache/plugin/PLUGIN_CACHE.md) and
[Ingredient Cache](../cache/ingredients/INGREDIENTS_CACHE.md) documents.

1. Each plugin's own ingredient and magic effect records are first
   parsed in isolation, computing each record's canonical identity:
   which plugin actually defines it, and a numeric id that stays stable
   regardless of which other plugin is referencing it. This step never
   looks at any other plugin, which is what makes its result safe to
   cache per plugin.
2. The whole active load order is then walked once, vanilla masters,
   then Creation Club content, then the user's own active plugin list,
   in that exact order, and every record of a type is indexed by that
   same canonical identity. When a later plugin in the load order
   defines a record with the same canonical identity as one an earlier
   plugin already indexed, a genuine override where the later plugin
   lists the earlier one as a master and reuses its record, the later
   entry replaces the earlier one in the index.

By the time the whole load order has been walked, every entry in the
index holds only its final, authoritative version, exactly how the game
engine itself resolves overrides, and exactly why an ingredient or
effect's recorded source plugin is the one that currently wins, not
necessarily the one that originally introduced it.

This part of the process is exact. It is not possible for a genuine
override to be mistaken for an unrelated new record, or the reverse,
because the canonical identity is derived from the same master-list
relative numbering the game itself uses, and it stays exact however many
plugins were reused from cache versus freshly parsed, since a cached
plugin's own canonical identities were computed the same way the last
time that plugin's bytes were actually read.

## 2. Where exactness stops: the final dictionaries are keyed by name

| Stage | Keyed by | Collision-free? |
| :--- | :--- | :--- |
| The index built in section 1 | Canonical identity | Yes |
| The final ingredient and effect databases | Resolved display name | No |

If two records with genuinely different, unrelated canonical identities,
no override relationship between them at all, happen to resolve to the
identical display string, only one of them survives in the final
result. The other is silently overwritten.

Which one wins is determined purely by processing order during that
pass, in practice whichever record is handled last, not necessarily the
one that is semantically correct or most recently overridden. It is
purely a name collision, independent of the override mechanism described
in section 1.

The effect database only ever includes magic effects actually referenced
by some ingredient, excluding the vast majority of magic effect records
in the game, enchantments, quest abilities, and so on, before they ever
reach the name-keyed dictionary. This substantially reduces exposure to
the risk above, since most magic effects never become collision
candidates in the first place, but it does not eliminate it: two
different ingredient-referenced effects, or two different ingredients,
can still coincidentally share a name.

## 3. Current mitigation: cross-reference the FormID manually

There is no automatic detection for two different, unrelated identities
resolving to the same name. A dropped duplicate is silent. Investigating
a suspected collision is a manual, three-step process:

1. Look up the entry's FormID in the ingredient or effect cache. Every
   ingredient and effect carries its winning plugin and FormID, see the
   [data sources](../data-sources/DATA_SOURCES.md) document's section 1.
2. Cross-reference that FormID against
   [xEdit](https://github.com/TES5Edit/TES5Edit), the community tool for
   reading and editing plugins that also documents the actual struct
   layout of every record type, or the mod's own documentation. If it
   does not match what was expected for that name, a different plugin's
   record won the name collision.
3. Reorder the affected plugins in the load order and rescan. This
   changes which record's name wins, as a workaround, the same as
   before, but now verifiable through the FormID instead of only
   inferring it from a missing entry.
