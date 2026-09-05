🌐 [English](PLUGIN_CACHE.md) · [Português](PLUGIN_CACHE.pt.md) · [Deutsch](PLUGIN_CACHE.de.md)

# Plugin Cache

This document describes the on-disk raw scan cache for a single plugin's
own ingredient and magic effect data: one small JSON file per active
plugin, at `cache/game_data/plugins/<plugin filename>.json`, named after
the plugin itself (for example `Skyrim.esm.json`).

Each file holds exactly what one plugin's own binary data contains: its
ingredient ([`INGR`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/INGR))
and magic effect
([`MGEF`](https://en.uesp.net/wiki/Skyrim_Mod:Mod_File_Format/MGEF))
records, already parsed and with display names resolved. It exists purely
to make rescanning fast. As long as a plugin's own bytes haven't changed,
its file here can be reused without reopening or re-parsing that plugin at
all.

## 1. Structure

```jsonc
{
  "signature": {
    "size": 249752131,
    "mtime": 1787841633.526221
  },
  "ingredients": [
    {
      "owner_file": "Skyrim.esm",
      "local_id": 1076764,
      "form_id": "00106E1C",
      "name": "Silverside Perch",
      "effect_refs": [
        {
          "effect_owner_file": "Skyrim.esm",
          "effect_local_id": 256790,
          "magnitude": 5.0,
          "duration": 0.0
        }
        // up to 4 entries, one per effect the ingredient has
      ]
    }
    // one entry per ingredient this plugin defines or overrides
  ],
  "effects": [
    {
      "owner_file": "Skyrim.esm",
      "local_id": 95196,
      "form_id": "000173DC",
      "name": "Banish - Damage Health",
      "cost": 0.0,
      "harmful": true
    }
    // one entry per magic effect this plugin defines or overrides
  ]
}
```

(Real excerpt, truncated, from a `Skyrim.esm.json` cache file.)

### 1.1 Signature

The signature is not a content hash: it is the plugin file's size in
bytes and last modified time, recorded at the moment this file was
scanned. A plain filesystem check against these two numbers, cheap
enough to run on every scan without opening the plugin itself, is enough
to tell whether the plugin has changed since. Any real edit to the
plugin, a mod update or a patch applied in an editing tool, changes at
least one of the two values.

A plugin that is listed as active but is not actually present on disk (a
routine situation under mod managers that list a plugin as active
without physically copying its file into the game's data folder) gets a
`size: -1, mtime: -1.0` signature instead, together with empty
`ingredients` and `effects` lists. That sentinel value stops every future
scan from repeatedly trying, and failing, to read a plugin that is
simply never going to be found on disk.

### 1.2 Ingredients

One entry per ingredient this plugin defines or overrides.

| Field | Read from | Meaning |
| :--- | :--- | :--- |
| `owner_file` | `INGR` record's own FormID, byte 3 (master index), resolved against this plugin's master list | The plugin that actually defines this ingredient, not necessarily the plugin this cache file belongs to. If this plugin only overrides an ingredient a master originally created, `owner_file` names that master instead. If this plugin created the ingredient in the first place, it names itself. |
| `local_id` | `INGR` record's own FormID, bytes 2-0 | A stable numeric identifier for the ingredient, unique together with `owner_file`. Unlike a raw FormID, this value does not change depending on which plugin is doing the referencing. See section 2.1 for why. |
| `form_id` | `INGR` record's own FormID, all 4 bytes, unmodified | The ingredient's FormID exactly as this specific plugin's own record stores it, useful for cross-checking against a plugin-editing tool. |
| `name` | `FULL` subrecord (literal text, or a string-table lookup for a localized plugin) | The ingredient's display name, exactly as the game shows it. |
| `effect_refs` | One `EFID`/`EFIT` subrecord pair per entry | Up to 4 entries, one per effect this ingredient produces. |

Each `effect_refs` entry describes one effect the ingredient produces,
with that ingredient's own strength for it.

| Field | Read from | Meaning |
| :--- | :--- | :--- |
| `effect_owner_file` | `EFID`, byte 3 (master index), resolved against this plugin's master list | The plugin where the magic effect is defined. |
| `effect_local_id` | `EFID`, bytes 2-0 | The stable numeric identifier for the magic effect. |
| `magnitude` | `EFIT` subrecord, bytes 0-3 (32-bit float) | How strong this ingredient's version of the effect is. |
| `duration` | `EFIT` subrecord, bytes 8-11 (32-bit integer) | How long this ingredient's version of the effect lasts. |

### 1.3 Effects

One entry per magic effect this plugin defines or overrides, every one
that exists in this plugin whether or not any ingredient actually uses
it.

| Field | Read from | Meaning |
| :--- | :--- | :--- |
| `owner_file` | `MGEF` record's own FormID, byte 3 (master index), resolved against this plugin's master list | The plugin that actually defines this magic effect, not necessarily the plugin this cache file belongs to. Same override rule as an ingredient's `owner_file`. |
| `local_id` | `MGEF` record's own FormID, bytes 2-0 | A stable numeric identifier for the magic effect, unique together with `owner_file`. |
| `form_id` | `MGEF` record's own FormID, all 4 bytes, unmodified | The effect's FormID as read from this plugin. |
| `name` | `FULL` subrecord | The effect's display name. |
| `cost` | `DATA` subrecord, bytes 4-7 (32-bit float) | The effect's base cost, a real property of the effect itself, used when valuing a potion. |
| `harmful` | `DATA` subrecord, bytes 0-3 (32-bit flags), bit `0x01` (Hostile) or `0x04` (Detrimental) | Whether the game classifies this as a harmful, poison-type effect. True if either bit is set. |

## 2. Where these values actually come from

None of the fields above are values this project invents: they are all
derived from bytes Bethesda's own plugin format already defines. This
project does not choose how a FormID is structured or how effect data is
laid out; it reads what is already there.

### 2.1 FormIDs and local identity

Every record, an ingredient, a magic effect, anything, has a 4-byte
FormID, split into two parts: the highest byte is a master index,
identifying the defining plugin's position in this record's own plugin's
master list, and the lower 3 bytes are the record's actual numeric id.

The master index byte is the catch: it is an index into a list that is
different for every plugin, since each plugin declares its own masters
in its own order. The exact same record can therefore have a completely
different raw FormID depending on which plugin is doing the pointing.
The master index byte only makes sense together with that specific
plugin's own master list.

`owner_file` and `local_id` sidestep that. `local_id` is just the lower
3 bytes, the part that never depends on any particular plugin's master
list, and `owner_file` is the actual filename the master index byte was
pointing at, resolved once for this cache entry using this plugin's own
master list. Together, `owner_file` and `local_id` identify a record the
same way no matter which plugin is referencing it, which is exactly what
is needed to recognize that two different plugins are referring to the
same ingredient or effect. The raw `form_id` field is kept alongside
this mainly so the exact bytes this plugin itself stored can still be
cross-checked against a plugin-editing tool.

### 2.2 An ingredient's own effect data

An ingredient's up to 4 effects come from up to 4 pairs of entries inside
its own record: an `EFID` entry (the referenced effect's FormID, split
the same way as above) immediately followed by an `EFIT` entry (12
bytes: a 32-bit magnitude, a 32-bit area, and a 32-bit duration, in that
order).

`magnitude` and `duration` are read straight out of those bytes, exactly
as the game stores them, with no scaling or rounding applied; this is
the only place either value comes from. There is no separate base
magnitude or duration anywhere in the plugin format that these are
relative to. Each ingredient's own `EFIT` bytes are already the
complete, absolute value. The area field exists in the same structure
but has no effect on potion value in this project's own calculations, so
it is read and immediately discarded.

The same underlying `DATA` structure is also how a magic effect's own
`cost` and `harmful` fields get read, on the `MGEF` record itself rather
than from any ingredient. See the [Effect Cache](../effects/EFFECTS_CACHE.md)
document for that layout.

## 3. How it is populated

A scan walks the full list of active plugins, in the order the game
itself would load them. For each one, it computes that plugin's current
signature and compares it against whatever is already cached.

If the signature is unchanged since last time, the cached file is reused
exactly as it is: the plugin's own binary data is never reopened, and
this file is left untouched on disk. If the signature has changed, or
nothing was cached before, the plugin's binary data (and its packed
resource archives, for any text stored outside the plugin itself) is
read fresh, and a new version of this file replaces the old one. If the
plugin is listed active but missing on disk, an empty snapshot is
written instead, with the sentinel signature from section 1.1.

Once every active plugin has an up to date snapshot this way, a plugin
that is no longer part of the active list at all, a mod that was
uninstalled or simply disabled, has its leftover cache file deleted
rather than left behind indefinitely.

Because only plugins that actually changed get reprocessed, a rescan
after a small change, one mod added or updated, only touches that one
mod's file and finishes almost instantly, instead of reprocessing every
active plugin every time. A full, from scratch rescan of everything can
still be forced when needed, for example if this cache is ever suspected
to be corrupted or out of sync.
