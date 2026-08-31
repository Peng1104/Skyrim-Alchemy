"""Skyrim alchemy potion optimization engine, using integer linear programming with PuLP."""

# External libraries
from pulp import (  # type: ignore
    PULP_CBC_CMD,
    LpAffineExpression,
    LpMaximize,
    LpProblem,
    LpStatusOptimal,
    LpVariable,
    lpSum,
)

# Local package modules (application)
from app.i18n import translate
from app.models import (
    Effect,
    Ingredient,
    InventoryIngredient,
    OptimizationResult,
    Potion,
    PotionValue,
    RecipeData,
    RecipeDetails,
)
from app.scraping import get_effects_data, get_ingredients_data


class AlchemyOptimizer:
    """
    Optimize potion creation using PuLP linear programming.

    Attributes
    ----------
    decimal_places : int
        Decimal precision for value calculations.
    effects_data : dict[str, Effect]
        Dictionary mapping effect names to Effects.
    ingredients_data : dict[str, Ingredient]
        Dictionary mapping ingredient names to Ingredients.
    missing_ingredients : list[str]
        List of ingredient names not found in data.
    """

    decimal_places: int
    effects_data: dict[str, Effect]
    ingredients_data: dict[str, Ingredient]
    missing_ingredients: list[str]

    def __init__(self, decimal_places: int = 3):
        """
        Initialize the optimizer with decimal precision.

        Parameters
        ----------
        decimal_places : int, optional
            Number of decimal places for value calculations, by default 3.
        """
        self.decimal_places = decimal_places
        self.effects_data = get_effects_data()
        self.ingredients_data = get_ingredients_data()
        self.missing_ingredients: list[str] = []

    def _convert_inventory(self, items: list[InventoryIngredient]) -> dict[str, int]:
        """
        Convert InventoryIngredient list to name -> quantity dictionary.

        Parameters
        ----------
        items : list[InventoryIngredient]
            List of inventory ingredients with quantities.

        Returns
        -------
        dict[str, int]
            Dictionary mapping ingredient names to quantities.
        """
        inventory: dict[str, int] = {}
        self.missing_ingredients = []

        for item in items:
            if item.name in self.ingredients_data:
                inventory[item.name] = item.amount
            else:
                self.missing_ingredients.append(item.name)

        return inventory

    def _generate_potions(self, inventory: dict[str, int]) -> list[PotionValue]:
        """
        Generate all possible valid potion combinations.

        Parameters
        ----------
        inventory : dict[str, int]
            Dictionary mapping ingredient names to quantities.

        Returns
        -------
        list[PotionValue]
            List of all valid potion combinations with their values.
        """
        valid_potions: list[PotionValue] = []
        ingredients = [
            self.ingredients_data[name]
            for name in inventory.keys()
            if name in self.ingredients_data
        ]

        # Generate all 2 and 3 ingredient combinations
        for i, ing1 in enumerate(ingredients):
            for j, ing2 in enumerate(ingredients[i+1:], i+1):
                # 2-ingredient combination
                potion = self._create_potion([ing1, ing2])
                if potion:
                    valid_potions.append(PotionValue(
                        potion=potion,
                        value=potion.value(self.decimal_places)
                    ))

                # 3-ingredient combinations
                for ing3 in ingredients[j+1:]:
                    potion = self._create_potion([ing1, ing2, ing3])
                    if potion:
                        valid_potions.append(PotionValue(
                            potion=potion,
                            value=potion.value(self.decimal_places)
                        ))

        return valid_potions

    def _create_potion(self, ingredients: list[Ingredient]) -> Potion | None:
        """
        Create a potion from ingredients, if valid.

        Parameters
        ----------
        ingredients : list[Ingredient]
            List of ingredients to combine.

        Returns
        -------
        Potion | None
            Valid potion if ingredients have shared effects, None otherwise.
        """
        if not 2 <= len(ingredients) <= 3:
            return None

        # Find shared effects
        effect_count: dict[str, int] = {}
        for ingredient in ingredients:
            for ing_effect in ingredient.effects:
                effect_count[ing_effect.name] = effect_count.get(
                    ing_effect.name, 0) + 1

        shared_effects = [
            self.effects_data[name] for name, count in effect_count.items()
            if count >= 2 and name in self.effects_data
        ]

        if not shared_effects:
            return None

        potion = Potion(ingredients=ingredients, effects=shared_effects)
        return potion if potion.valid() else None

    def _optimize(
            self,
            potions: list[PotionValue],
            inventory: dict[str, int]
    ) -> list[PotionValue]:
        """
        Optimize potion selection using PuLP linear programming.

        Parameters
        ----------
        potions : list[PotionValue]
            List of all valid potion combinations.
        inventory : dict[str, int]
            Dictionary mapping ingredient names to quantities.

        Returns
        -------
        list[PotionValue]
            Optimally selected potions based on maximum value.
        """
        if not potions:
            return []

        # Step 1: Remove duplicates
        unique_potions = self._remove_duplicates(potions)

        # Step 2: Set up and solve optimization problem
        prob, variables = self._create_problem(unique_potions, inventory)
        prob.solve(PULP_CBC_CMD(msg=False))  # type: ignore[attr-defined]

        # Step 3: Extract solution
        return self._extract_solution(prob, variables, unique_potions)

    def _remove_duplicates(self, potions: list[PotionValue]) -> list[PotionValue]:
        """
        Remove duplicate potions keeping highest value.

        Parameters
        ----------
        potions : list[PotionValue]
            List of potions that may contain duplicates.

        Returns
        -------
        list[PotionValue]
            List of unique potions with highest values retained.
        """
        unique: dict[tuple[str, ...], PotionValue] = {}
        for potion in potions:
            key = tuple(
                sorted([ing.name for ing in potion.potion.ingredients]))
            if key not in unique or potion.value > unique[key].value:
                unique[key] = potion
        return list(unique.values())

    def _create_problem(
        self,
        potions: list[PotionValue],
        inventory: dict[str, int]
    ) -> tuple[LpProblem, dict[int, LpVariable]]:
        """
        Create PuLP optimization problem with variables and constraints.

        Parameters
        ----------
        potions : list[PotionValue]
            List of unique potions to optimize.
        inventory : dict[str, int]
            Dictionary mapping ingredient names to quantities.

        Returns
        -------
        tuple[LpProblem, dict[int, LpVariable]]
            PuLP problem and decision variables.
        """
        variables: dict[int, LpVariable] = {}

        for i, _ in enumerate(potions):
            variables[i] = LpVariable(
                f"potion_{i}", lowBound=0, cat='Integer')  # type: ignore

        objective: list[LpAffineExpression] = [
            variables[i] * potion.value for i, potion in enumerate(potions)
        ]

        prob = LpProblem("Potion_Optimization", LpMaximize)

        prob += (lpSum(objective), "Total_Value")

        self._add_constraints(prob, variables, potions, inventory)

        return prob, variables

    def _add_constraints(
        self,
        prob: LpProblem,
        variables: dict[int, LpVariable],
        potions: list[PotionValue],
        inventory: dict[str, int]
    ):
        """
        Add ingredient availability constraints to the problem.

        Parameters
        ----------
        prob : LpProblem
            PuLP problem object.
        variables : dict[int, LpVariable]
            Decision variables for each potion.
        potions : list[PotionValue]
            List of potions to constrain.
        inventory : dict[str, int]
            Available ingredient quantities.
        """
        for name, amount in inventory.items():
            terms: list[LpAffineExpression] = []

            for i, potion in enumerate(potions):
                count = sum(
                    1 for ing in potion.potion.ingredients if ing.name == name)
                if count > 0:
                    terms.append(variables[i] * count)  # type: ignore[attr-defined]

            if terms:
                prob += (lpSum(terms) <= amount, f"Constraint_{name}")  # noqa: S1481

    def _extract_solution(self, prob: LpProblem, variables: dict[int, LpVariable],
                          potions: list[PotionValue]) -> list[PotionValue]:
        """
        Extract optimal solution from solved problem.

        Parameters
        ----------
        prob : LpProblem
            Solved PuLP problem object.
        variables : dict[int, LpVariable]
            Decision variables for each potion.
        potions : list[PotionValue]
            List of potions corresponding to variables.

        Returns
        -------
        list[PotionValue]
            Selected potions from optimal solution.
        """
        selected: list[PotionValue] = []
        if getattr(prob, 'status', None) == LpStatusOptimal:
            for i, potion in enumerate(potions):
                count = int(getattr(variables[i], 'varValue', 0) or 0)
                selected.extend([potion] * count)
        return selected

    def _build_recipes(self, selected: list[PotionValue]) -> list[RecipeDetails]:
        """
        Build final recipe sequence from selected potions.

        Parameters
        ----------
        selected : list[PotionValue]
            Potions selected by optimization.

        Returns
        -------
        list[RecipeDetails]
            Ordered sequence of recipes with counts and details.
        """
        if not selected:
            return []

        # Group identical recipes
        recipes: dict[tuple[str, ...], RecipeData] = {}
        for potion in selected:
            key = tuple(
                sorted([ing.name for ing in potion.potion.ingredients]))

            if key not in recipes:
                recipes[key] = RecipeData(
                    ingredients=sorted(
                        [ing.name for ing in potion.potion.ingredients]),
                    effects=sorted(
                        [eff.name for eff in potion.potion.effects]),
                    value=potion.value,
                    count=0
                )
            recipes[key].count += 1

        # Sort by value and create sequence
        sequence: list[RecipeDetails] = []
        for i, (_, recipe) in enumerate(
            sorted(recipes.items(), key=lambda x: x[1].value, reverse=True), 1
        ):
            sequence.append(RecipeDetails(
                order=i,
                count=recipe.count,
                ingredients=recipe.ingredients,
                effects=recipe.effects,
                value=recipe.value
            ))

        return sequence

    def run_optimization(self, items: list[InventoryIngredient]) -> OptimizationResult:
        """
        Run the complete optimization pipeline.

        Parameters
        ----------
        items : list[InventoryIngredient]
            List of available ingredients with quantities.

        Returns
        -------
        OptimizationResult
            Complete optimization results with recipes and remaining ingredients.
        """
        # Step 1: Convert inventory
        inventory = self._convert_inventory(items)

        # Step 2: Generate all valid potion combinations
        all_potions = self._generate_potions(inventory)

        # Step 3: Optimize with PuLP
        if not all_potions:
            selected = []
        else:
            selected = self._optimize(all_potions, inventory)

        # Step 4: Build recipe sequence
        recipes = self._build_recipes(selected)

        # Step 5: Calculate remaining ingredients
        remaining = inventory.copy()

        for potion in selected:
            for ingredient in potion.potion.ingredients:
                remaining[ingredient.name] = remaining.get(
                    ingredient.name, 0) - 1

        remaining = {name: amount for name,
                     amount in remaining.items() if amount > 0}

        return OptimizationResult(
            fabrication_sequence=recipes,
            remaining_ingredients=remaining
        )

    def show_missing_warning(self):
        """Display a warning about ingredients not found in data."""
        if self.missing_ingredients:
            print(translate(
                "missing_ingredients_warning", count=len(self.missing_ingredients)
            ))
            for ingredient_name in self.missing_ingredients:
                print(translate("missing_ingredient_line", name=ingredient_name))
            print("\n" + "="*100 + "\n")
