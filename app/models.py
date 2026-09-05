"""Module containing the data models for the Skyrim inventory app."""
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


class ModPluginSignature(BaseModel):
    """Model representing one plugin's cache-invalidation signature."""

    size: int = Field(..., description="The plugin file's size in bytes, at scan time.")
    mtime: float = Field(..., description="The plugin file's last-modified time, at scan time.")


class RawEffectRef(BaseModel):
    """
    One `EFID`+`EFIT` entry from an ingredient record, not yet effect-name resolved.

    The effect it refers to can be defined in a completely different plugin
    than the ingredient itself - resolving its display name requires the
    full, cross-plugin canonical index (see `app.game_data._scan`), so it's
    deferred to the merge step. Everything here, in contrast, only depends
    on the owning ingredient's own plugin (`resolve_form_id` against that
    plugin's own masters), which is what makes `RawIngredientRecord` safe to
    cache and reuse across scans without re-reading that plugin.
    """

    effect_owner_file: str = Field(
        ..., description="Canonical defining-plugin filename of the referenced effect.")
    effect_local_id: int = Field(
        ..., description="Canonical local FormID of the referenced effect within "
                          "effect_owner_file.")
    magnitude: float = Field(..., description="This ingredient's own EFIT magnitude.")
    duration: float = Field(..., description="This ingredient's own EFIT duration.")


class RawIngredientRecord(BaseModel):
    """
    One `INGR` record's own canonical identity and already-resolved data.

    Everything here comes from the record's own plugin alone (display name
    resolution, FormID canonicalization) - independent of every other
    plugin in the load order, and independent of which plugin ultimately
    wins the override for this record's canonical identity. That's what
    makes it safe to cache per plugin and reuse across scans: as long as
    the defining plugin's own bytes haven't changed, this snapshot doesn't
    need to be rebuilt, no matter what else in the load order did change.
    """

    owner_file: str = Field(..., description="Canonical defining-plugin filename.")
    local_id: int = Field(..., description="Canonical local FormID within owner_file.")
    form_id: str = Field(..., description="Full FormID (hex string) as read from this "
                                           "specific plugin's own record.")
    name: str = Field(..., description="Resolved display name (FULL).")
    effect_refs: list[RawEffectRef] = Field(
        ..., description="This record's own EFID+EFIT entries, effect names not yet "
                          "resolved (see RawEffectRef).")


class RawEffectRecord(BaseModel):
    """
    One `MGEF` record's own canonical identity and already-resolved data.

    Same rationale as `RawIngredientRecord` - everything here is intrinsic
    to the record's own defining plugin, so it's safe to cache per plugin.
    """

    owner_file: str = Field(..., description="Canonical defining-plugin filename.")
    local_id: int = Field(..., description="Canonical local FormID within owner_file.")
    form_id: str = Field(..., description="Full FormID (hex string) as read from this "
                                           "specific plugin's own record.")
    name: str = Field(..., description="Resolved display name (FULL).")
    cost: float = Field(..., description="MGEF.DATA Base Cost.")
    harmful: bool = Field(..., description="MGEF.DATA Hostile/Detrimental flag bits.")


class PluginGameDataSnapshot(BaseModel):
    """
    Everything one plugin itself contributes to the game-data scan.

    Cacheable independently of every other plugin in the load order - none
    of this depends on load order or on any other plugin's content, only on
    this plugin's own bytes (tracked via `signature`). This is what makes
    an incremental rescan possible: a plugin whose signature hasn't changed
    since the last scan can reuse its cached snapshot verbatim, skipping
    the actual binary/BSA parsing - only the (cheap, in-memory) merge step
    that resolves overrides and effect-name cross-references across the
    whole load order needs to run every time.
    """

    signature: ModPluginSignature = Field(
        ..., description="This plugin's cache-invalidation signature at snapshot time.")
    ingredients: list[RawIngredientRecord] = Field(
        ..., description="Every INGR record this plugin itself defines or overrides.")
    effects: list[RawEffectRecord] = Field(
        ..., description="Every MGEF record this plugin itself defines or overrides.")


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


class IngredientEffect(BaseModel):
    """Model representing an effect of a Skyrim ingredient, with its own real EFIT values."""

    name: str = Field(..., description="Name of the effect")
    magnitude: float = Field(
        ..., description="This ingredient's own EFIT magnitude for the effect - a real, "
                          "absolute value read directly from the ingredient's own binary "
                          "record, not a ratio against any shared 'base' (no such base "
                          "exists in the game's data - see app.models.Effect).")
    duration: float = Field(
        ..., description="This ingredient's own EFIT duration for the effect - same as "
                          "magnitude, a real absolute value, not a ratio.")


class Ingredient(BaseModel):
    """Model representing a Skyrim ingredient."""

    name: str = Field(..., description="Name of the ingredient")
    effects: list[IngredientEffect] = Field(
        ..., description="List of effects associated with the ingredient")
    source_file: str = Field(
        ..., description="Plugin filename that defines this ingredient's authoritative "
                          "(post-override) version, e.g. 'Skyrim.esm'. Informational only "
                          "- never used in any calculation.")
    form_id: str = Field(
        ..., description="This ingredient's full FormID (hex string, e.g. '0006BC02'), "
                          "as defined in source_file. Informational only.")


class Effect(BaseModel):
    """
    Model representing a Skyrim magic effect.

    Only holds what's actually a real property of the effect itself, per the
    `MGEF` record's own `DATA` subrecord: `cost` (Base Cost, byte offset 4)
    and `harmful` (the Hostile/Detrimental flag bits). There is deliberately
    no `magnitude`/`duration` here - those aren't properties of the effect at
    all, they belong to each ingredient's own `EFIT` (see `IngredientEffect`).
    """

    name: str = Field(..., description="Name of the effect")
    cost: float = Field(..., description="The effect's base cost (MGEF.DATA Base Cost)")
    harmful: bool = Field(
        default=False,
        description="Whether this is a harmful (poison-type) effect, per the MGEF.DATA "
                    "Flags' Hostile or Detrimental bit.",
    )
    source_file: str = Field(
        ..., description="Plugin filename that defines this effect's authoritative "
                          "(post-override) version, e.g. 'Skyrim.esm'. Informational only "
                          "- never used in any calculation.")
    form_id: str = Field(
        ..., description="This effect's full FormID (hex string, e.g. '00073F2B'), as "
                          "defined in source_file. Informational only.")

    def base_value(self, decimal_places: int = 0) -> float:
        """
        Calculate a reference value for this effect, at magnitude=1/instant duration.

        Only meaningful as a rough magnitude-free comparison point (e.g. for
        ranking newly-discovered effects) - real potion values always go
        through `value()` with the winning ingredient's actual magnitude/duration.

        Parameters
        ----------
        decimal_places : int, optional
            Number of decimal places for precision, by default 0.

        Returns
        -------
        float
            The effect's value at magnitude=1, duration=0 (instant).
        """
        return self.value(1.0, 0.0, decimal_places)

    def value(self, magnitude: float, duration: float, decimal_places: int = 0) -> float:
        """
        Calculate the effect's value for a given (absolute) magnitude and duration.

        Parameters
        ----------
        magnitude : float
            The effective magnitude to value (the winning ingredient's own
            EFIT magnitude, already perk-adjusted by the caller if applicable).
        duration : float
            The effective duration to value, same provenance as magnitude.
        decimal_places : int, optional
            Number of decimal places for precision, by default 0.

        Returns
        -------
        float
            Calculated value of the effect with specified decimal precision.
        """
        if duration < 1:
            cost = self.cost * max(magnitude**1.1, 1)

        else:
            # A perk (Purity) can drive duration to 0 even for effects that
            # normally have a duration; when that happens the duration term drops
            # out entirely (factor 1) instead of zeroing the whole cost.
            duration_term = (duration / 10) ** 1.1 if duration > 0 else 1.0

            cost = self.cost * max(magnitude**1.1, 1) * duration_term

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

    def get_winning_effect(self, effect: Effect) -> tuple[float, float]:
        """
        Get the (magnitude, duration) of a shared effect's single winning ingredient.

        When ingredients have different strengths for a shared effect, the
        game does not combine their EFIT values - it uses only the single
        ingredient whose (magnitude, duration), run through the value
        formula, produces the highest value, discarding the rest (verified
        empirically against UESP's own per-effect "Priority"/"Gold Mult"
        tables, e.g. Skyrim:Damage_Health - Jarrin Root's magnitude=200
        outranks River Betty's magnitude=5, and Nirnroot's instant duration=0
        outranks several higher-magnitude timed ingredients because the
        value formula's duration term collapses for instant effects). This
        is resolved fresh, per potion, directly from each contributing
        ingredient's own real EFIT data - there is no separate "priority
        table" to look up.

        Parameters
        ----------
        effect : Effect
            The effect to resolve.

        Returns
        -------
        tuple[float, float]
            The winning ingredient's (magnitude, duration), or (0.0, 0.0) if
            no ingredient in this potion actually has this effect.
        """
        contributing: list[tuple[float, float]] = [
            (ing_effect.magnitude, ing_effect.duration)
            for ingredient in self.ingredients
            for ing_effect in ingredient.effects
            if ing_effect.name == effect.name
        ]

        if not contributing:
            return (0.0, 0.0)

        # High decimal_places here is just for ranking precision (avoids ties from
        # rounding); the actual (magnitude, duration) returned are unrounded.
        return max(contributing, key=lambda md: effect.value(*md, 6))

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
            effect.name: effect.value(*self.get_winning_effect(effect), decimal_places)
            for effect in self.effects
        }
        is_poison = classify_mixture(self.effects, raw_values)

        for effect in self.effects:
            magnitude, duration = self.get_winning_effect(effect)
            adjusted = apply_perk_modifiers(effect, magnitude, duration, is_poison, perks)

            if adjusted is None:
                # Purity stripped this effect out of the mixture entirely -
                # it contributes nothing, not even the effect's base cost.
                continue

            magnitude, duration = adjusted
            value += effect.value(magnitude, duration, decimal_places)

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
