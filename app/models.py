"""Module containing the data models for the Skyrim inventory app."""
from enum import StrEnum
from math import floor

from pydantic import BaseModel, Field

from app.perks import PerkConfig, apply_perk_modifiers, classify_mixture


class InventoryIngredient(BaseModel):
    """Model representing an Ingredient in the inventory."""

    name: str = Field(..., description="Name of the ingredient")
    amount: int = Field(..., description="Amount of the ingredient")


class InventoryMarker(BaseModel):
    """Model representing the on-disk marker for the last combined screenshot range."""

    processed_screenshot_ids: list[int] = Field(
        ..., description="Every screenshot ID included in the most recent `retrieve` "
                          "call, whatever range it covered - not just the highest one, "
                          "so gaps in the numbering are represented accurately. Each "
                          "screenshot's own OCR result is cached separately (see "
                          "app.inventory._inventory), so this is informational "
                          "bookkeeping only - it is not required to determine what needs "
                          "OCR. Used by `Inventory.resolve_new_range` to pick the range "
                          "for a default (no explicit --min/--max) run.")


class ScreenshotStatus(BaseModel):
    """Model representing one screenshot ID's availability, for `--list`."""

    id: int = Field(..., description="The screenshot's ID.")
    has_image: bool = Field(
        ..., description="Whether the source screenshot file still exists in the "
                          "game directory.")
    has_cache: bool = Field(
        ..., description="Whether this screenshot's OCR result is cached on disk.")


class ScreenshotDetail(ScreenshotStatus):
    """Model representing one screenshot's availability plus its cached ingredients (`--info`)."""

    ingredients: list[InventoryIngredient] = Field(
        ..., description="This screenshot's cached OCR result, or an empty list "
                          "if it has no cache yet (has_cache is False).")


class Modifier(StrEnum):
    """Enum representing the type of modifier for an ingredient."""

    MAGNITUDE = "Magnitude"
    VALUE = "Value"
    DURATION = "Duration"


class IngredientEffect(BaseModel):
    """Model representing an effect of a Skyrim ingredient."""

    name: str = Field(..., description="Name of the effect")
    modifiers: dict[Modifier, float] | None = Field(
        ..., description="List of modifiers associated with the effect")

    def cost_factor(self) -> float:
        """
        Get the cost factor for the effect based on its modifiers.

        Returns
        -------
        float
            The cost factor, or 1.0 if no cost modifier is present.
        """
        if not self.modifiers:
            return 1.0

        factor = self.modifiers.get(  # pylint: disable=no-member
            Modifier.VALUE, None)

        return factor if factor is not None else 1.0

    def magnitude_factor(self) -> float:
        """
        Get the magnitude factor for the effect based on its modifiers.

        Returns
        -------
        float
            The magnitude factor, or 1.0 if no magnitude modifier is present.
        """
        if not self.modifiers:
            return 1.0

        factor = self.modifiers.get(  # pylint: disable=no-member
            Modifier.MAGNITUDE, None)

        return factor if factor is not None else 1.0

    def duration_factor(self) -> float:
        """
        Get the duration factor for the effect based on its modifiers.

        Returns
        -------
        float
            The duration factor, or 1.0 if no duration modifier is present.
        """
        if not self.modifiers:
            return 1.0

        factor = self.modifiers.get(  # pylint: disable=no-member
            Modifier.DURATION, None)

        return factor if factor is not None else 1.0


class Ingredient(BaseModel):
    """Model representing a Skyrim ingredient."""

    name: str = Field(..., description="Name of the ingredient")
    effects: list[IngredientEffect] = Field(
        ..., description="List of effects associated with the ingredient")


class Effect(BaseModel):
    """Model representing an effect of a Skyrim ingredient."""

    name: str = Field(..., description="Name of the effect")
    cost: float = Field(..., description="The base cost of the effect")
    magnitude: float = Field(...,
                             description="The base magnitude of the effect")
    duration: float = Field(..., description="The base duration of the effect")
    harmful: bool = Field(
        default=False,
        description="Whether this is a harmful (poison-type) effect, per UESP's "
                    "EffectNeg/EffectPos row classification.",
    )
    priority_overrides: dict[str, tuple[float, float]] = Field(
        default_factory=dict,
        description="Maps ingredient name to (magnitude_ratio, duration_ratio) for "
                    "ingredients with non-standard strength for this effect (e.g. "
                    "River Betty for Damage Health). See app.scraping._effect_priorities.",
    )

    def base_value(self, decimal_places: int = 0) -> float:
        """
        Calculate the base value of the effect based on its cost, magnitude, and duration.

        Parameters
        ----------
        decimal_places : int, optional
            Number of decimal places for precision, by default 0.

        Returns
        -------
        float
            The base value of the effect with specified decimal precision.
        """
        return self.value(1, 1, 1, decimal_places)

    def value(
        self,
        cost_factor: float,
        magnitude_factor: float,
        duration_factor: float,
        decimal_places: int = 0
    ) -> float:
        """
        Calculate the value of the effect based on its cost, magnitude, and duration.

        Parameters
        ----------
        cost_factor : float
            Factor to adjust the cost.
        magnitude_factor : float
            Factor to adjust the magnitude.
        duration_factor : float
            Factor to adjust the duration.
        decimal_places : int, optional
            Number of decimal places for precision, by default 0.

        Returns
        -------
        float
            Calculated value of the effect with specified decimal precision.
        """
        magnitude = self.magnitude * magnitude_factor

        if self.duration < 1:
            cost = self.cost * max(magnitude**1.1, 1)

        else:
            duration = self.duration * duration_factor
            # A perk (Purity) can drive duration_factor to 0 even for effects that
            # normally have a duration; when that happens the duration term drops
            # out entirely (factor 1) instead of zeroing the whole cost.
            duration_term = (duration / 10) ** 1.1 if duration > 0 else 1.0

            cost = self.cost * max(magnitude**1.1, 1) * duration_term

        if cost_factor != 1:
            cost = cost * cost_factor

        if decimal_places == 0:
            return floor(cost)

        multiplier = 10 ** decimal_places

        return floor(cost * multiplier) / multiplier


class Potion(BaseModel):
    """Model representing a potion."""

    ingredients: list[Ingredient] = Field(
        ..., description="List of ingredients used in the potion")
    effects: list[Effect] = Field(
        ..., description="List of effects of the potion")

    def is_effect_present(self, effect: Effect) -> bool:
        """
        Check if an effect is shared by at least 2 of the potion's ingredients.

        Parameters
        ----------
        effect : Effect
            The effect to check for.

        Returns
        -------
        bool
            True if the effect is present, False otherwise.
        """
        return sum(
            1 for ingredient in self.ingredients
            if any(eff.name == effect.name for eff in ingredient.effects)
        ) >= 2

    def shares_effect(self, ingredient: Ingredient) -> bool:
        """
        Check if an ingredient shares at least one effect with another ingredient in the potion.

        Parameters
        ----------
        ingredient : Ingredient
            The ingredient to check against.

        Returns
        -------
        bool
            True if the ingredient shares an effect with another ingredient, False otherwise.
        """
        effects = {effect.name for effect in ingredient.effects}

        for potion_ingredient in self.ingredients:
            if potion_ingredient is ingredient:
                continue

            if effects.intersection({eff.name for eff in potion_ingredient.effects}):
                return True

        return False

    def valid(self) -> bool:
        """
        Check if the potion is valid.

        A potion is valid when it has 2 or 3 ingredients, has at least 1 effect,
        each effect is present in at least 2 ingredients, and each ingredient
        shares at least one effect with another ingredient.

        Returns
        -------
        bool
            True if the potion passes all validation rules, False otherwise.
        """
        # Rule 1: Must have 2 or 3 ingredients
        if not 2 <= len(self.ingredients) <= 3:
            return False

        # Rule 2: Must have at least 1 effect
        if not self.effects:
            return False

        # Rule 3: Each effect must be present in at least 2 ingredients
        if not all(self.is_effect_present(effect) for effect in self.effects):
            return False

        # Rule 4: Each ingredient must share at least one effect with another ingredient
        if not all(self.shares_effect(ingredient) for ingredient in self.ingredients):
            return False

        return True

    def get_modifiers(self, effect: Effect) -> tuple[float, float, float]:
        """
        Get the modifiers for a specific effect, from its single highest-priority ingredient.

        When ingredients have non-standard (modified) strengths for a shared
        effect, the game does not combine their modifiers independently - it
        uses the cost/magnitude/duration triple from a single "priority"
        ingredient and discards the others entirely (see `effect.priority_overrides`,
        scraped from the effect's own UESP page). For ingredients with no such
        override, falls back to the "Value"-icon modifiers from the ingredients
        page. Priority is resolved by picking whichever contributing ingredient
        produces the highest resulting effect value: e.g. for Damage Health,
        River Betty outranks Nirnroot, so a potion combining both uses only
        River Betty's modifiers.

        Parameters
        ----------
        effect : Effect
            The effect to find modifiers for.

        Returns
        -------
        tuple[float, float, float]
            The (cost_factor, magnitude_factor, duration_factor) of the
            single highest-priority contributing ingredient, or (1.0, 1.0, 1.0)
            if every contributing ingredient is standard (unmodified).
        """
        contributing: list[tuple[float, float, float]] = []

        for ingredient in self.ingredients:
            for ing_effect in ingredient.effects:
                if ing_effect.name != effect.name:
                    continue

                override = effect.priority_overrides.get(ingredient.name)

                if override is not None:
                    magnitude_ratio, duration_ratio = override
                    contributing.append((1.0, magnitude_ratio, duration_ratio))
                else:
                    contributing.append((
                        ing_effect.cost_factor(),
                        ing_effect.magnitude_factor(),
                        ing_effect.duration_factor(),
                    ))

        if not contributing:
            return (1.0, 1.0, 1.0)

        # High decimal_places here is just for ranking precision (avoids ties from
        # rounding); the actual factors returned are unrounded.
        return max(contributing, key=lambda modifiers: effect.value(*modifiers, 6))

    def value(self, perks: PerkConfig, decimal_places: int = 0) -> float:
        """
        Calculate the value of the potion based on its effects.

        Parameters
        ----------
        perks : PerkConfig
            Which alchemy perks are active for this calculation.
        decimal_places : int, optional
            Number of decimal places for precision, by default 0.

        Returns
        -------
        float
            The total value of the potion.
        """
        value = 0.0

        if not self.valid():
            return value

        raw_values = {
            effect.name: effect.value(*self.get_modifiers(effect), decimal_places)
            for effect in self.effects
        }
        is_poison = classify_mixture(self.effects, raw_values)

        for effect in self.effects:
            cost_factor, magnitude_factor, duration_factor = self.get_modifiers(effect)
            magnitude_factor, duration_factor = apply_perk_modifiers(
                effect, magnitude_factor, duration_factor, is_poison, perks
            )
            value += effect.value(cost_factor, magnitude_factor, duration_factor, decimal_places)

        return value

class PotionValue(BaseModel):
    """Model representing a potion with its value."""

    potion: Potion
    value: float


class FabricationResult(BaseModel):
    """Model representing the result of potion fabrication."""

    total_potions: int
    selected_potions: list[PotionValue]
    remaining_ingredients: dict[str, int]


class RecipeDetails(BaseModel):
    """Model representing the details of a recipe."""

    order: int
    count: int
    ingredients: list[str]
    effects: list[str]
    value: float


class OptimizationResult(BaseModel):
    """Model representing the result of the optimization."""

    fabrication_sequence: list[RecipeDetails]
    remaining_ingredients: dict[str, int]


class RecipeData(BaseModel):
    """Model representing recipe data during processing."""

    ingredients: list[str]
    effects: list[str]
    value: float
    count: int
