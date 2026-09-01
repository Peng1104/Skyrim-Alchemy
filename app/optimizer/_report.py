"""Console reporting for the optimization pipeline (CLI-style formatted output)."""
from app.i18n import translate
from app.models import InventoryIngredient
from app.optimizer._engine import AlchemyOptimizer
from app.perks import PerkConfig, active_perk_names, perk_config_from_settings


def execute(
    items: list[InventoryIngredient],
    optimizer: AlchemyOptimizer | None = None,
    perks: PerkConfig | None = None,
):
    """
    Perform the actual optimization and print the results.

    Parameters
    ----------
    items : list[InventoryIngredient]
        List of inventory ingredients with quantities.
    optimizer : AlchemyOptimizer | None, optional
        Optimizer instance to reuse, avoiding re-scraping UESP data when the
        caller already built one. Creates a new one if not provided, by default None.
    perks : PerkConfig | None, optional
        Which alchemy perks are active. Defaults to the perks configured in
        `Settings` (config.toml/env vars) when not given - this is the CLI's
        only remaining dependency on global perk settings.
    """
    perks = perks if perks is not None else perk_config_from_settings()
    print("=" * 100 + "\n")
    print(translate("inventory_initial_header"))

    for item in items:
        print(translate("ingredient_line", name=item.name, amount=item.amount))

    if not items:
        print(translate("no_ingredients_found"))
        print("\n" + "=" * 100)
        return

    print("\n" + "=" * 100 + "\n")
    print(translate("starting_effects_analysis"))

    perk_names = active_perk_names(perks)
    if perk_names:
        print(translate("active_perks", perks=", ".join(perk_names)))
    else:
        print(translate("no_active_perks"))

    print("\n" + "=" * 100 + "\n")

    if optimizer is None:
        optimizer = AlchemyOptimizer(decimal_places=3)

    result = optimizer.run_optimization(items, perks)

    if not result.fabrication_sequence:
        print(translate("no_potions_fabricated"))
        print("\n" + "=" * 100)
        return

    print(translate("fabrication_stats_header"))
    print(translate("total_recipes", count=len(result.fabrication_sequence)))
    print(translate(
        "total_potions",
        count=sum(recipe.count for recipe in result.fabrication_sequence),
    ))
    print("\n" + "=" * 100 + "\n")

    print(translate("fabrication_sequence_header"))

    for recipe in result.fabrication_sequence:
        print(translate(
            "recipe_line", order=recipe.order, count=recipe.count, ingredients=recipe.ingredients
        ))

    print("\n" + "=" * 100)

    if result.remaining_ingredients:
        print(translate("remaining_ingredients_header"))

        for ingredient_name, amount in result.remaining_ingredients.items():
            print(translate("ingredient_line", name=ingredient_name, amount=amount))

    else:
        print(translate("all_ingredients_used"))

    print("\n" + "=" * 100)

    optimizer.show_missing_warning()
