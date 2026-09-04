"""
Orchestrates the full ingredient/effect database scan and its on-disk cache.

Reads *every* active plugin uniformly - vanilla masters, DLCs, Creation Club
content, and third-party mods - via the same binary `.esp/.esm/.esl/.bsa`
reading built in this package, resolving `FormID` overrides across the whole
load order (the last-loaded plugin to touch a given record wins, exactly how
the game engine itself resolves overrides). There is no wiki involved - this
is the only source of ingredient/effect data for the whole project.

Scanning is incremental per plugin: each plugin's own binary/BSA data is
parsed into a `PluginGameDataSnapshot` (see `app.models`) that depends only
on that plugin's own bytes, cached under its own cache-invalidation
signature. A plugin whose signature hasn't changed since the last scan
reuses its cached snapshot verbatim - only the plugins that actually
changed get re-parsed. The (cheap, in-memory, no I/O beyond that) merge step
that resolves overrides and effect-name cross-references across the whole
load order still runs every scan, over whatever mix of cached and freshly
parsed snapshots the load order needs.
"""
import json
from pathlib import Path

from app.cache import GAME_DATA_CACHE_DIRECTORY
from app.game_data._load_order import (
    parse_active_plugins,
    parse_ccc,
    resolve_ccc_path,
    resolve_plugins_txt,
)
from app.game_data._plugin_records import (
    get_edid,
    get_effect_entries,
    get_full_raw,
    get_masters,
    get_mgef_base_cost,
    get_mgef_harmful,
    iter_records_of_type,
    load_plugin,
    resolve_form_id,
)
from app.game_data._strings import resolve_full
from app.i18n import translate
from app.models import (
    Effect,
    Ingredient,
    IngredientEffect,
    ModPluginSignature,
    PluginGameDataSnapshot,
    RawEffectRecord,
    RawEffectRef,
    RawIngredientRecord,
)

# Masters always load before any Plugins.txt-listed plugin, in this fixed
# relative order, regardless of what's in Plugins.txt (they're never listed
# there at all - confirmed empirically against a real Plugins.txt this
# session). Only the ones actually present get included (e.g. no DLC owned).
_VANILLA_MASTERS_ORDER = [
    "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm",
]

_SNAPSHOTS_DIR = GAME_DATA_CACHE_DIRECTORY / "plugins"
_INGREDIENTS_FILE = GAME_DATA_CACHE_DIRECTORY / "ingredients.json"
_EFFECTS_FILE = GAME_DATA_CACHE_DIRECTORY / "effects.json"

# Canonical (owner_file, local_id) -> the record and the plugin filename
# currently providing it (the override winner, not necessarily owner_file).
_IngrIndexEntry = tuple[RawIngredientRecord, str]
_EffIndexEntry = tuple[RawEffectRecord, str]


def _index_data_dir_case_insensitively(data_dir: Path) -> dict[str, str]:
    """
    Map every plugin filename in `Data/` to its exact on-disk casing, lowercased key.

    `Skyrim.ccc` and the vanilla masters list are written with Bethesda's own
    mixed-case filenames (e.g. `ccBGSSSE037-Curios.esl`); on a case-sensitive
    filesystem (ext4 - common for a Steam library shared with Windows on
    Linux, unlike NTFS/Windows' own case-insensitive default) the actual file
    on disk can be lowercased instead (`ccbgssse037-curios.esl`). A plain
    `.exists()` check against the `.ccc`/masters spelling then silently
    excludes the plugin from the whole scan - confirmed empirically: 74 of 75
    `Skyrim.ccc` entries in a real install failed an exact-case `.exists()`
    check this way, and any of their ingredients not overridden by some other
    active plugin (so never read through another plugin's own, correctly
    cased, master list) were silently missing from the ingredient database.

    Parameters
    ----------
    data_dir : Path
        The game's `Data` directory.

    Returns
    -------
    dict[str, str]
        Lowercased filename -> the exact filename as it exists on disk.
    """
    return {entry.name.lower(): entry.name for entry in data_dir.iterdir() if entry.is_file()}


def _resolve_load_order(game_directory: str, plugins_txt: Path, data_dir: Path) -> list[str]:
    """
    Get the full plugin load order: vanilla masters, `Skyrim.ccc`, then `Plugins.txt`.

    Parameters
    ----------
    game_directory : str
        Path to the Skyrim game installation directory (for `Skyrim.ccc`).
    plugins_txt : Path
        The resolved `Plugins.txt`.
    data_dir : Path
        The game's `Data` directory.

    Returns
    -------
    list[str]
        Filenames in load order - each in its *actual on-disk* casing (see
        `_index_data_dir_case_insensitively`) - masters that exist on disk,
        then every plugin listed in `Skyrim.ccc` (Creation Club content the
        game auto-loads independently of `Plugins.txt` - confirmed
        empirically: a CC pack can be "enabled" in-game with no entry at
        all, active or disabled, in a Mod Organizer 2 profile's
        `Plugins.txt`), then every active plugin from `Plugins.txt` itself.
        Deduplicated (case-insensitively) - a plugin already added from an
        earlier source is not added again.
    """
    disk_names = _index_data_dir_case_insensitively(data_dir)
    load_order: list[str] = []
    seen: set[str] = set()

    def _add(names: list[str]) -> None:
        for name in names:
            actual = disk_names.get(name.lower())

            if actual is not None and actual.lower() not in seen:
                load_order.append(actual)
                seen.add(actual.lower())

    _add(_VANILLA_MASTERS_ORDER)
    _add(parse_ccc(resolve_ccc_path(game_directory)))
    _add(parse_active_plugins(plugins_txt))

    return load_order


def _snapshot_path(plugin_filename: str) -> Path:
    """
    Get the cache file path for one plugin's snapshot.

    Parameters
    ----------
    plugin_filename : str
        The plugin's filename (e.g. `"ccbgssse037-curios.esl"`).

    Returns
    -------
    Path
        `cache/game_data/plugins/<plugin_filename>.json` - Bethesda plugin
        filenames never contain characters that are unsafe in a filename,
        so no escaping is needed.
    """
    return _SNAPSHOTS_DIR / f"{plugin_filename}.json"


def _load_snapshots() -> dict[str, PluginGameDataSnapshot]:
    """
    Load every cached per-plugin snapshot, if present.

    One small JSON file per plugin, rather than one large file for every
    plugin combined - lets a rescan write only the files for plugins that
    actually changed (see `_save_snapshots`), and keeps any single file a
    manageable size for manual inspection if ever needed.

    Returns
    -------
    dict[str, PluginGameDataSnapshot]
        Plugin filename -> its last cached snapshot. A plugin with no
        cache file yet, or a malformed one, is simply absent - treated the
        same as "never scanned" by the caller, forcing just that plugin to
        be rescanned rather than the whole cache.
    """
    if not _SNAPSHOTS_DIR.is_dir():
        return {}

    snapshots: dict[str, PluginGameDataSnapshot] = {}

    for path in _SNAPSHOTS_DIR.glob("*.json"):
        plugin_filename = path.name.removesuffix(".json")

        try:
            with open(path, "r") as f:
                snapshots[plugin_filename] = PluginGameDataSnapshot.model_validate(json.load(f))
        except (json.JSONDecodeError, ValueError):
            continue

    return snapshots


def _save_snapshots(to_write: dict[str, PluginGameDataSnapshot], removed: set[str]) -> None:
    """
    Persist only the plugin snapshots that actually changed this scan.

    A plugin whose cached snapshot was reused verbatim (its signature still
    matched) is never in `to_write` and its file is left untouched - a
    rescan after changing one plugin only ever rewrites that one plugin's
    cache file, not every plugin's.

    Parameters
    ----------
    to_write : dict[str, PluginGameDataSnapshot]
        New or updated snapshots from this scan, filename -> snapshot.
    removed : set[str]
        Plugin filenames no longer in the current load order (mod
        uninstalled, or `Plugins.txt`/`Skyrim.ccc` no longer lists it) -
        their cache files are deleted rather than left to linger forever.
    """
    if to_write:
        _SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    for filename, snapshot in to_write.items():
        with open(_snapshot_path(filename), "w") as f:
            json.dump(snapshot.model_dump(), f, indent=2)

    for filename in removed:
        _snapshot_path(filename).unlink(missing_ok=True)


def _load_cached_ingredients() -> dict[str, Ingredient]:
    """
    Load the cached ingredient database, if present.

    Returns
    -------
    dict[str, Ingredient]
        Cached ingredients, or an empty dict if there's no cache yet.
    """
    if not _INGREDIENTS_FILE.exists():
        return {}

    with open(_INGREDIENTS_FILE, "r") as f:
        return {name: Ingredient.model_validate(data) for name, data in json.load(f).items()}


def _load_cached_effects() -> dict[str, Effect]:
    """
    Load the cached effect database, if present.

    Returns
    -------
    dict[str, Effect]
        Cached effects, or an empty dict if there's no cache yet.
    """
    if not _EFFECTS_FILE.exists():
        return {}

    with open(_EFFECTS_FILE, "r") as f:
        return {name: Effect.model_validate(data) for name, data in json.load(f).items()}


def _save_results(ingredients: dict[str, Ingredient], effects: dict[str, Effect]) -> None:
    """
    Persist the scan's full ingredient/effect database.

    Parameters
    ----------
    ingredients : dict[str, Ingredient]
        Every resolved ingredient.
    effects : dict[str, Effect]
        Every resolved effect.
    """
    with open(_INGREDIENTS_FILE, "w") as f:
        json.dump({name: ing.model_dump() for name, ing in ingredients.items()}, f, indent=2)

    with open(_EFFECTS_FILE, "w") as f:
        json.dump({name: eff.model_dump() for name, eff in effects.items()}, f, indent=2)


def _plugin_signature(plugin_path: Path) -> ModPluginSignature:
    """
    Compute a plugin's current cache-invalidation signature.

    Parameters
    ----------
    plugin_path : Path
        Path the plugin would live at, whether or not it actually exists.

    Returns
    -------
    ModPluginSignature
        The real size/mtime, or a `(-1, -1.0)` sentinel if the plugin isn't
        physically present - active in `Plugins.txt`/`Skyrim.ccc` but not
        under `Data` is common under Mod Organizer 2, which virtualizes
        most mods' files at runtime instead of copying them into the real
        `Data` directory.
    """
    if not plugin_path.exists():
        return ModPluginSignature(size=-1, mtime=-1.0)

    stat = plugin_path.stat()

    return ModPluginSignature(size=stat.st_size, mtime=stat.st_mtime)


def _scan_plugin(plugin_path: Path, signature: ModPluginSignature) -> PluginGameDataSnapshot | None:
    """
    Parse one plugin's own `INGR`/`MGEF` records into a cacheable snapshot.

    Every field resolved here (display names, canonical FormIDs) depends
    only on this plugin's own bytes and its own BSA(s) - never on any other
    plugin in the load order - which is exactly what makes the resulting
    snapshot safe to cache and reuse verbatim on a later scan where this
    plugin hasn't changed. An ingredient's effect names are the one thing
    *not* resolved here (see `app.models.RawEffectRef`): the effect a given
    `EFID` refers to can be defined in a completely different plugin, so
    resolving it needs the full, cross-plugin canonical index - that only
    exists during the merge step (`_merge_snapshots`), after every plugin's
    snapshot (cached or freshly parsed) is known.

    Parameters
    ----------
    plugin_path : Path
        Path to the plugin file (already confirmed to exist by the caller).
    signature : ModPluginSignature
        This plugin's current cache-invalidation signature, stashed on the
        resulting snapshot so a later scan can tell whether it's still
        fresh without re-parsing anything.

    Returns
    -------
    PluginGameDataSnapshot | None
        The parsed snapshot, or None if the plugin couldn't be read at all.
    """
    try:
        plugin = load_plugin(plugin_path)
    except Exception:
        print(translate("game_data_scan_plugin_unreadable", filename=plugin_path.name))
        return None

    filename = plugin_path.name
    masters = get_masters(plugin)

    raw_ingredients: list[RawIngredientRecord] = []

    for record in iter_records_of_type(plugin, "INGR"):
        name = resolve_full(get_full_raw(record), plugin_path)

        if name is None:
            print(translate(
                "game_data_ingredient_unresolved",
                edid=get_edid(record) or "?",
                filename=filename,
            ))
            continue

        owner_file, local_id = resolve_form_id(int(record.formid, base=16), masters, filename)

        effect_refs: list[RawEffectRef] = []

        for effect_form_id, (magnitude, _area, duration) in get_effect_entries(record):
            effect_owner, effect_local = resolve_form_id(effect_form_id, masters, filename)
            effect_refs.append(RawEffectRef(
                effect_owner_file=effect_owner, effect_local_id=effect_local,
                magnitude=magnitude, duration=float(duration),
            ))

        raw_ingredients.append(RawIngredientRecord(
            owner_file=owner_file, local_id=local_id, form_id=record.formid,
            name=name, effect_refs=effect_refs,
        ))

    raw_effects: list[RawEffectRecord] = []

    for record in iter_records_of_type(plugin, "MGEF"):
        name = resolve_full(get_full_raw(record), plugin_path)

        if name is None:
            continue

        owner_file, local_id = resolve_form_id(int(record.formid, base=16), masters, filename)

        raw_effects.append(RawEffectRecord(
            owner_file=owner_file, local_id=local_id, form_id=record.formid, name=name,
            cost=get_mgef_base_cost(record) or 0.0, harmful=get_mgef_harmful(record),
        ))

    return PluginGameDataSnapshot(
        signature=signature, ingredients=raw_ingredients, effects=raw_effects)


def _merge_snapshots(
    load_order: list[str],
    snapshots: dict[str, PluginGameDataSnapshot],
) -> tuple[dict[str, Ingredient], dict[str, Effect]]:
    """
    Resolve every plugin's snapshot into the final, override-resolved, name-keyed database.

    Purely in-memory - no binary/BSA I/O happens here, regardless of how
    many plugins were freshly parsed vs. reused from cache. One pass over
    `load_order` builds the canonical override index (a later plugin's
    entry for the same `(owner_file, local_id)` replaces an earlier one,
    same as the game engine resolving overrides); a second pass resolves
    each ingredient's effect references against that index and builds the
    final `Ingredient`/`Effect` objects.

    Deliberately does **not** turn every `RawEffectRecord` into an `Effect`
    - the game defines many thousands of `MGEF` records that have nothing
    to do with alchemy (enchantments, quest/scripted abilities, etc.), and
    some of those happen to share display text with a real alchemy effect
    (e.g. Dragonborn.esm's own quest-only `DLC2TTR4aAbDamageHealth`
    resolves to the text "Damage Health", same as the real
    `AlchDamageHealth` from `Skyrim.esm`, with a different `cost`). Deriving
    `effects` only from what ingredients actually reference avoids pulling
    in any such unrelated `MGEF` in the first place - a real name collision
    between two effects *both* actually used by some ingredient can still
    happen (same documented limitation as ingredient-name collisions, see
    docs/game_data/), but that's a much narrower, rarer case.

    Parameters
    ----------
    load_order : list[str]
        Plugin filenames in load order (see `_resolve_load_order`).
    snapshots : dict[str, PluginGameDataSnapshot]
        Every plugin's snapshot (cached or freshly parsed) that's actually
        needed for this load order - a plugin missing from this dict (never
        successfully parsed, and not cached) simply contributes nothing.

    Returns
    -------
    tuple[dict[str, Ingredient], dict[str, Effect]]
        Every resolved ingredient, and every effect actually referenced by
        at least one of them - both keyed by display name.
    """
    ingr_index: dict[tuple[str, int], _IngrIndexEntry] = {}
    mgef_index: dict[tuple[str, int], _EffIndexEntry] = {}

    for filename in load_order:
        snapshot = snapshots.get(filename)

        if snapshot is None:
            continue

        for raw_ing in snapshot.ingredients:
            ingr_index[(raw_ing.owner_file, raw_ing.local_id)] = (raw_ing, filename)

        for raw_eff in snapshot.effects:
            mgef_index[(raw_eff.owner_file, raw_eff.local_id)] = (raw_eff, filename)

    ingredients: dict[str, Ingredient] = {}
    effects: dict[str, Effect] = {}

    for raw_ing, provider in ingr_index.values():
        ingredient_effects: list[IngredientEffect] = []

        for ref in raw_ing.effect_refs:
            mgef_entry = mgef_index.get((ref.effect_owner_file, ref.effect_local_id))

            if mgef_entry is None:
                continue

            raw_eff, eff_provider = mgef_entry

            ingredient_effects.append(IngredientEffect(
                name=raw_eff.name, magnitude=ref.magnitude, duration=ref.duration))

            effects[raw_eff.name] = Effect(
                name=raw_eff.name, cost=raw_eff.cost, harmful=raw_eff.harmful,
                source_file=eff_provider, form_id=raw_eff.form_id,
            )

        ingredients[raw_ing.name] = Ingredient(
            name=raw_ing.name, effects=ingredient_effects,
            source_file=provider, form_id=raw_ing.form_id,
        )

    return ingredients, effects


def scan_game_data(
    game_directory: str,
    *,
    plugins_txt_override: str | None = None,
    force: bool = False,
) -> tuple[dict[str, Ingredient], dict[str, Effect]]:
    """
    Build the complete ingredient/effect database from every active plugin.

    Covers vanilla masters, DLCs, Creation Club content, and third-party
    mods uniformly - no wiki involved, this is the only data source. Cached
    under `cache/game_data/`; scanning is incremental per plugin (see the
    module docstring) - a plugin unchanged since the last scan (by its
    size/mtime signature) isn't re-parsed unless `force=True`.

    Parameters
    ----------
    game_directory : str
        Path to the Skyrim game installation directory.
    plugins_txt_override : str | None, optional
        Explicit `Plugins.txt` path (from `Settings.plugins_txt_path`),
        bypassing auto-detection.
    force : bool, optional
        Ignore every cached snapshot and re-parse every plugin from
        scratch, by default False.

    Returns
    -------
    tuple[dict[str, Ingredient], dict[str, Effect]]
        The complete ingredient and effect databases.
    """
    plugins_txt = resolve_plugins_txt(plugins_txt_override)

    if plugins_txt is None:
        print(translate("game_data_scan_no_plugins_txt"))
        return _load_cached_ingredients(), _load_cached_effects()

    data_dir = Path(game_directory) / "Data"
    load_order = _resolve_load_order(game_directory, plugins_txt, data_dir)

    cached_snapshots = {} if force else _load_snapshots()
    snapshots: dict[str, PluginGameDataSnapshot] = {}
    to_write: dict[str, PluginGameDataSnapshot] = {}
    removed = set(cached_snapshots) - set(load_order)
    any_changed = force or bool(removed)

    for filename in load_order:
        plugin_path = data_dir / filename
        signature = _plugin_signature(plugin_path)
        cached = None if force else cached_snapshots.get(filename)

        if cached is not None and cached.signature == signature:
            snapshots[filename] = cached
            continue

        any_changed = True

        if signature.size == -1:
            # Active but not physically present under Data (MO2
            # virtualization) - nothing to parse. Still cached (with the
            # sentinel signature) so this doesn't force a rescan attempt on
            # every subsequent run.
            snapshots[filename] = PluginGameDataSnapshot(
                signature=signature, ingredients=[], effects=[])
            to_write[filename] = snapshots[filename]
            continue

        scanned = _scan_plugin(plugin_path, signature)

        if scanned is not None:
            snapshots[filename] = scanned
            to_write[filename] = scanned

    if not any_changed:
        ingredients = _load_cached_ingredients()
        effects = _load_cached_effects()

        if ingredients:
            print(translate("game_data_scan_no_changes", count=len(ingredients)))
            return ingredients, effects

    ingredients, effects = _merge_snapshots(load_order, snapshots)

    _save_snapshots(to_write, removed)
    _save_results(ingredients, effects)
    print(translate("game_data_scan_complete", ingredients=len(ingredients), effects=len(effects)))

    return ingredients, effects
