# Binary-reading dependencies: `sse-plugin-interface` and `sse-bsa`

This document describes a risk assumed knowingly by this project: the two
third-party libraries `app/game_data/` relies on for reading Skyrim's own
binary formats are both relatively new and lightly used, and this document
records exactly what was verified about them, and what happens if a plugin
or BSA hits a format variation they don't cover.

## 1. What each library does, and why the risk exists

- **`sse-plugin-interface`** (`app/game_data/_plugin_records.py`) parses
  `.esp`/`.esm`/`.esl` plugin files: record/subrecord structure, `TES4`
  headers, master lists, `FormID`s.
- **`sse-bsa`** (`app/game_data/_bsa.py`) parses `.bsa` archives, used to
  extract `.strings` files for localized text (see
  [DATA_SOURCES.md §1.2](../data-sources/DATA_SOURCES.md#12-localized-strings-and-the-dlc-bsa-fallback)).

Both are pure-Python implementations of Bethesda's undocumented,
reverse-engineered binary formats, maintained by small open-source projects
with relatively few commits/stars on GitHub compared to, say, `pydantic` or
`requests`. That's a real risk for a project that now depends on them for
its *only* source of ingredient/effect data (see
[DATA_SOURCES.md §0](../data-sources/DATA_SOURCES.md#0-why-not-the-wiki)) -
a format variation neither library handles could silently produce wrong or
missing data instead of a clean error, if nothing else guarded against it.

## 2. What was actually verified

This wasn't taken on faith. Both libraries were exercised end-to-end this
session against the two real cases that matter most in practice, on a real,
heavily modded install (~170 active plugins):

- **A small, unofficial, non-localized mod**: `whitewind player home.esp`
  (a hobby mod, not an official Bethesda/CC release). Its ingredient's
  `FULL` subrecord holds **literal text** (`"Frozen Bee"`) directly in the
  record - no BSA involved at all, exercising `sse-plugin-interface`'s
  record/subrecord parsing on its own, on a plugin built by a completely
  different, non-professional pipeline than Bethesda's own tools.
- **An official, localized Creation Club release**: `ccbgssse037-curios.esl`
  (Curios). Its ingredients' `FULL` subrecords hold **numeric localized
  string IDs** (e.g. `7`), requiring `sse-bsa` to open
  `ccbgssse037-curios.bsa`, extract `strings/ccbgssse037-curios_english.strings`,
  and `sse-plugin-interface`'s own string-ID handling to resolve the record
  correctly - exercising both libraries together, on a plugin built by
  Bethesda's own official pipeline.

Both cases matched expectations exactly (verified against known ingredient
names, `EFIT` values, and - for Curios specifically - cross-checked against
an in-game console `help` command's own FormID output, see
[DATA_SOURCES.md §1.3](../data-sources/DATA_SOURCES.md#13-creation-club-and-skyrimccc)).
Combined with the full 218-ingredient/65-effect scan across every plugin in
a real load order matching known reference values (vanilla, DLC, and
several other CC/mod ingredients spot-checked individually during this
session's development), this covers the two structurally different ways a
`FULL` subrecord can be encoded - which is the actual axis of risk for
these libraries, not any one specific plugin's polish or size.

## 3. What happens when a variation isn't covered

Nothing has been observed that these libraries fail to parse. But the
scanner is deliberately built so that if one ever does turn up, it fails
**loudly for that one ingredient**, never silently:

- `resolve_full` (`app/game_data/_strings.py`) returns `None` whenever it
  can't resolve a `FULL` value - a missing `.strings` entry, an
  unparseable BSA, or any other failure collapses to this same `None`,
  never a wrong guess.
- `_scan_plugin` (`app/game_data/_scan.py`) checks for exactly that: an
  ingredient whose name doesn't resolve prints
  `game_data_ingredient_unresolved` (with the record's `EDID` and defining
  plugin, so it's traceable) and is **skipped** - it never enters
  `ingredients.json` with a wrong or blank name.
- A plugin that fails to load at all (`load_plugin` raising, e.g. a
  genuinely corrupt or unsupported file) prints
  `game_data_scan_plugin_unreadable` and that whole plugin is skipped, same
  principle at a coarser grain.

In both cases the scan continues for every other plugin/ingredient - one
unparseable record or plugin doesn't abort the whole run, and the failure
is always visible in the console/log output, never swallowed.

## 4. Version pinning

`pyproject.toml` currently declares open-ended lower bounds:

```toml
"sse-plugin-interface>=1.0.1",
"sse-bsa>=1.1.0",
```

`uv.lock` resolves these to exact versions (`1.0.1` and `1.1.0` as of this
writing) and `uv sync` installs exactly what the lockfile says, so a normal
install is already reproducible. The `>=` bound in `pyproject.toml` itself,
though, does not prevent a future `uv lock --upgrade` from silently pulling
in a newer major version of either library without a deliberate decision to
do so - for most dependencies that's fine, but for two libraries this
project has no fallback for (there's no wiki to fall back to anymore) and
that are maintained by small, low-activity projects, an unreviewed major
bump is exactly the kind of change that should require a conscious
decision, not happen as a side effect of upgrading an unrelated package.
Pin them with `==` instead of `>=` the next time either is touched, so a
version bump for these two specifically always goes through an explicit,
reviewed `pyproject.toml` edit.
