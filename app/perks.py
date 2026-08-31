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
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from app.models import Effect

_PERK_BONUS = 1.25  # +25%, per UESP's PowerFactor formula

# Physician only applies to these three effects (MagicAlchRestoreHealth/Magicka/Stamina).
_RESTORE_EFFECTS: frozenset[str] = frozenset({
    "Restore Health", "Restore Magicka", "Restore Stamina",
})

# PowerFactor scales duration instead of magnitude for these effects only.
_DURATION_SCALING_EFFECTS: frozenset[str] = frozenset({
    "Invisibility", "Paralysis", "Slow", "Waterbreathing",
})


def active_perk_names() -> list[str]:
    """
    List the currently configured (enabled) alchemy perks.

    Returns
    -------
    list[str]
        Names of the enabled perks, in a fixed order. Empty if none are enabled.
    """
    settings = get_settings()
    names: list[str] = []

    if settings.perk_physician:
        names.append("Physician")
    if settings.perk_benefactor:
        names.append("Benefactor")
    if settings.perk_poisoner:
        names.append("Poisoner")
    if settings.perk_purity:
        names.append("Purity")

    return names


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
    magnitude_factor: float,
    duration_factor: float,
    is_poison: bool,
) -> tuple[float, float]:
    """
    Apply the configured Physician/Benefactor/Poisoner/Purity bonuses to an effect.

    Parameters
    ----------
    effect : Effect
        The effect being adjusted.
    magnitude_factor : float
        Magnitude factor from ingredient modifiers, before perks.
    duration_factor : float
        Duration factor from ingredient modifiers, before perks.
    is_poison : bool
        Whether the overall mixture was classified as a poison (see `classify_mixture`).

    Returns
    -------
    tuple[float, float]
        The perk-adjusted (magnitude_factor, duration_factor).
    """
    settings = get_settings()

    if settings.perk_purity and effect.harmful != is_poison:
        # Purity: harmful effect in a potion, or beneficial effect in a poison -
        # its properties are set to zero (collapses to just the effect's base cost).
        return 0.0, 0.0

    multiplier = 1.0

    if settings.perk_physician and effect.name in _RESTORE_EFFECTS:
        multiplier *= _PERK_BONUS

    if is_poison and settings.perk_poisoner and effect.harmful:
        multiplier *= _PERK_BONUS
    elif not is_poison and settings.perk_benefactor and not effect.harmful:
        multiplier *= _PERK_BONUS

    if effect.name in _DURATION_SCALING_EFFECTS:
        return magnitude_factor, duration_factor * multiplier

    return magnitude_factor * multiplier, duration_factor
