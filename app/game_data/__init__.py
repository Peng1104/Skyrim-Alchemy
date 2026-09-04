"""
Complete ingredient/effect database, read directly from plugin binary data.

Reads every active plugin's binary data (`.esp/.esm/.esl/.bsa`), never a
wiki - see `_scan.py` for the override-aware scan itself.

Only the CLI calls `scan_game_data` (it has a local `game_directory`); the
API only ever calls `load_cached_game_data`, which reads the cache the CLI
already produced and never touches the game files itself.
"""
import json

from app.cache import GAME_DATA_CACHE_DIRECTORY
from app.game_data._scan import scan_game_data
from app.models import Effect, Ingredient

_INGREDIENTS_FILE = GAME_DATA_CACHE_DIRECTORY / "ingredients.json"
_EFFECTS_FILE = GAME_DATA_CACHE_DIRECTORY / "effects.json"

__all__ = ["GameDataNotCachedError", "load_cached_game_data", "scan_game_data"]


class GameDataNotCachedError(RuntimeError):
    """
    Raised when `cache/game_data/` doesn't exist yet.

    The API must never scan `.esm` files itself (it has no local game
    install) - this tells a caller like `app.api` to fail loudly at startup
    instead of running with an empty ingredient/effect database.
    """


def load_cached_game_data() -> tuple[dict[str, Ingredient], dict[str, Effect]]:
    """
    Load the ingredient/effect database straight from `cache/game_data/`.

    Never scans - a pure cache read, safe to call from a process with no
    access to a local Skyrim install (e.g. the API).

    Returns
    -------
    tuple[dict[str, Ingredient], dict[str, Effect]]
        The cached ingredient and effect databases.

    Raises
    ------
    GameDataNotCachedError
        If `cache/game_data/ingredients.json` doesn't exist yet - the CLI
        must be run with `--refresh` against a local Skyrim install first.
    """
    if not _INGREDIENTS_FILE.exists():
        raise GameDataNotCachedError(
            "cache/game_data/ingredients.json not found - run the CLI "
            "(cli.py --refresh) against a local Skyrim install first."
        )

    with open(_INGREDIENTS_FILE, "r") as f:
        ingredients = {
            name: Ingredient.model_validate(data) for name, data in json.load(f).items()
        }

    effects: dict[str, Effect] = {}

    if _EFFECTS_FILE.exists():
        with open(_EFFECTS_FILE, "r") as f:
            effects = {name: Effect.model_validate(data) for name, data in json.load(f).items()}

    return ingredients, effects
