"""
Alchemy perk modeling: Physician, Benefactor, Poisoner, and Purity.

Follows UESP's documented PowerFactor formula. Explicitly NOT modeled (out of
scope for this feature): Alchemy skill, the Alchemist perk, Fortify Alchemy
gear, and the Seeker of Shadows (Dragonborn) ability - all of those apply
uniformly across every effect, so omitting them does not change which effect
or recipe is favored relative to another, only the absolute gold numbers.

Physician/Benefactor/Poisoner/Purity, by contrast, apply *conditionally* per
effect (only to Restore effects, or only to the majority polarity of the
mixture), so they can change which recipe the optimizer prefers - hence the
config flags in `app.config.Settings`.
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from app.models import Effect

_PERK_BONUS = 1.25  # +25%, per UESP's PowerFactor formula


@dataclass(frozen=True)
class PerkConfig:
    """
    Which alchemy perks are active, threaded explicitly through a single calculation.

    Passed explicitly (never read from global `Settings`) so that concurrent
    API requests with different perk selections can't race or clobber each
    other. The CLI still sources this from `Settings` - see
    `perk_config_from_settings`.
    """

    physician: bool = False
    benefactor: bool = False
    poisoner: bool = False
    purity: bool = False

# Physician only applies to these three effects (MagicAlchRestoreHealth/Magicka/Stamina).
_RESTORE_EFFECTS: frozenset[str] = frozenset({
    "Restore Health", "Restore Magicka", "Restore Stamina",
})

# PowerFactor scales duration instead of magnitude for these effects only.
_DURATION_SCALING_EFFECTS: frozenset[str] = frozenset({
    "Invisibility", "Paralysis", "Slow", "Waterbreathing",
})


def active_perk_names(perks: PerkConfig) -> list[str]:
    """
    List the currently configured (enabled) alchemy perks.

    Parameters
    ----------
    perks : PerkConfig
        Which perks are active.

    Returns
    -------
    list[str]
        Names of the enabled perks, in a fixed order. Empty if none are enabled.
    """
    names: list[str] = []

    if perks.physician:
        names.append("Physician")
    if perks.benefactor:
        names.append("Benefactor")
    if perks.poisoner:
        names.append("Poisoner")
    if perks.purity:
        names.append("Purity")

    return names


def perk_config_from_settings() -> PerkConfig:
    """
    Build a `PerkConfig` from the global `Settings` (CLI/local-run path only).

    The API path must never call this - perks arrive explicitly per request
    instead. This is the single point where the CLI's perk configuration
    still flows from `Settings` (config.toml/env vars).

    Returns
    -------
    PerkConfig
        The perk configuration read from `Settings`.
    """
    settings = get_settings()

    return PerkConfig(
        physician=settings.perk_physician,
        benefactor=settings.perk_benefactor,
        poisoner=settings.perk_poisoner,
        purity=settings.perk_purity,
    )


def classify_mixture(effects: list["Effect"], raw_values: dict[str, float]) -> bool:
    """
    Determine whether a potion is classified as a poison or a potion.

    Matches the game's rule: the single effect with the highest gold value,
    computed WITHOUT any perk bonus, decides whether the whole mixture is
    treated as a potion or a poison for Benefactor/Poisoner/Purity purposes.

    Parameters
    ----------
    effects : list[Effect]
        The potion's effects.
    raw_values : dict[str, float]
        Each effect's gold value computed without perk bonuses, keyed by effect name.

    Returns
    -------
    bool
        True if the mixture is a poison (its dominant effect is harmful).
    """
    dominant = max(effects, key=lambda effect: raw_values[effect.name])
    return dominant.harmful


def apply_perk_modifiers(
    effect: "Effect",
    magnitude: float,
    duration: float,
    is_poison: bool,
    perks: PerkConfig,
) -> tuple[float, float] | None:
    """
    Apply the configured Physician/Benefactor/Poisoner/Purity bonuses to an effect.

    Parameters
    ----------
    effect : Effect
        The effect being adjusted.
    magnitude : float
        The winning ingredient's magnitude for this effect, before perks
        (see `Potion.get_winning_effect`).
    duration : float
        The winning ingredient's duration for this effect, before perks.
    is_poison : bool
        Whether the overall mixture was classified as a poison (see `classify_mixture`).
    perks : PerkConfig
        Which perks are active for this calculation.

    Returns
    -------
    tuple[float, float] | None
        The perk-adjusted (magnitude, duration), or None if Purity strips this
        effect out of the potion entirely (see below) - the caller must treat
        None as a zero contribution to the potion's value, not fall through to
        `Effect.value(0, 0)` (which would floor to the effect's base cost
        instead of zero, per the auto-calc formula's own `Magnitude < 1 -> 1`/
        `Duration 0 -> 10` floors).
    """
    if perks.purity and effect.harmful != is_poison:
        # Purity: a harmful effect in a potion, or a beneficial effect in a
        # poison, is removed from the mixture outright, with no compensating
        # bonus elsewhere - it contributes nothing to the potion's value.
        return None

    multiplier = 1.0

    if perks.physician and effect.name in _RESTORE_EFFECTS:
        multiplier *= _PERK_BONUS

    if is_poison and perks.poisoner and effect.harmful:
        multiplier *= _PERK_BONUS
    elif not is_poison and perks.benefactor and not effect.harmful:
        multiplier *= _PERK_BONUS

    if effect.name in _DURATION_SCALING_EFFECTS:
        return magnitude, duration * multiplier

    return magnitude * multiplier, duration
