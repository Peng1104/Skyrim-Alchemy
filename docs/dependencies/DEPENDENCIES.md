# Binary-reading dependencies

This document describes a risk assumed knowingly by this project. The
two third-party libraries the game-data scan relies on for reading
Skyrim's own binary formats are both relatively new and lightly used, and
this document records what was verified about them, and what happens if a
plugin or archive hits a format variation they do not cover.

## 1. What each library does, and why the risk exists

[`sse-plugin-interface`](https://github.com/cutleast/sse-plugin-interface)
parses plugin files themselves: record and subrecord structure, headers,
master lists, FormIDs.
[`sse-bsa`](https://github.com/cutleast/sse-bsa) parses the game's packed
resource archives, used to extract localized text files (see the
[data sources](../data-sources/DATA_SOURCES.md) document's section 1.2).

Both are pure Python implementations of Bethesda's undocumented,
reverse-engineered binary formats, maintained by the same author,
[cutleast](https://github.com/cutleast), as small open-source projects
with relatively few contributions compared to a widely used
general-purpose library. That is a real risk for a project that now
depends on them for its only source of ingredient and effect data (see
the [data sources](../data-sources/DATA_SOURCES.md) document). A format
variation neither library handles could silently produce
wrong or missing data instead of a clean error, if nothing else guarded
against it.

## 2. What was actually verified

This was not taken on faith. Both libraries were exercised end to end
against the two real cases that matter most in practice, on a real,
heavily modded install with around 170 active plugins.

| | Plugin type | Display text encoding | Library exercised |
| :--- | :--- | :--- | :--- |
| Case 1 | Small, unofficial, non-localized mod (a hobby creation, not an official Bethesda or Creation Club release) | Literal text, stored directly in the record, no archive involved | Plugin-parsing library only |
| Case 2 | Official, localized Creation Club release | Numeric localized string id, resolved through the plugin's own packed archive | Plugin-parsing library and archive-parsing library together |

Both cases matched expectations exactly, verified against known
ingredient names and effect values, and for the Creation Club case,
cross-checked against an in-game console command's own FormID output.
Combined with a full 218-ingredient, 65-effect scan across every plugin
in a real load order matching known reference values, vanilla, DLC, and
several other Creation Club and mod ingredients spot-checked
individually, this covers the two structurally different ways display
text can be encoded, which is the actual axis of risk for these
libraries, not any one specific plugin's polish or size.

## 3. What happens when a variation is not covered

Nothing has been observed that these libraries fail to parse. The
scanner is deliberately built so that if one ever does turn up, it fails
loudly for that one ingredient, never silently.

| Failure | Behavior |
| :--- | :--- |
| A record's display name cannot be resolved (missing string entry, unparseable archive, or any other cause) | Collapses to the same empty result, never a wrong guess. The ingredient is logged, with its own internal identifier and defining plugin so it is traceable, and skipped. It never enters the final ingredient database with a wrong or blank name. |
| A plugin fails to load at all (a genuinely corrupt or unsupported file) | Logged, and that whole plugin is skipped, the same principle at a coarser grain. |

In both cases the scan continues for every other plugin and ingredient.
One unparseable record or plugin does not abort the whole run, and the
failure is always visible in the console or log output, never
swallowed.

## 4. Version pinning

The project's dependency list currently declares open-ended lower bounds
for both libraries, and the lockfile resolves these to exact versions, so
a normal install is already reproducible. The open-ended bound itself,
though, does not prevent a future dependency upgrade from silently
pulling in a newer major version of either library without a deliberate
decision to do so. For most dependencies that is fine, but for two
libraries this project has no fallback for, there is no wiki to fall back
to anymore, and that are maintained by small, low-activity projects, an
unreviewed major version bump is exactly the kind of change that should
require a conscious decision, not happen as a side effect of upgrading an
unrelated package. Pinning them to an exact version the next time either
is touched would make sure a version bump for these two specifically
always goes through an explicit, reviewed change.
