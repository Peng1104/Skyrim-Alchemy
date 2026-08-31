"""Test script - CLI run without spinning up the API server."""
import argparse

from app.config import get_settings
from app.i18n import translate
from app.inventory import Inventory
from app.logger import ConsoleCapture
from app.optimizer import AlchemyOptimizer, execute


def _parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments (`min`, `max`, `refresh`, `delete_old`).
    """
    parser = argparse.ArgumentParser(description="Skyrim Alchemy Optimizer - CLI")
    parser.add_argument(
        "--min", type=int, default=None,
        help="Lowest screenshot ID to combine. Defaults to 0 (the whole history).",
    )
    parser.add_argument(
        "--max", type=int, default=None,
        help="Highest screenshot ID to combine. Defaults to the newest screenshot found.",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Ignore the per-screenshot cache within the selected range and re-run OCR.",
    )
    parser.add_argument(
        "--delete-old", action="store_true",
        help="Delete screenshots that already have a cached OCR result.",
    )

    return parser.parse_args()


def main() -> None:
    """Run the CLI: read the inventory (OCR or cache) and print the optimized recipes."""
    args = _parse_args()

    settings = get_settings()
    optimizer = AlchemyOptimizer(decimal_places=3)
    inventory = Inventory(settings.game_directory)

    with ConsoleCapture():
        print(translate("analyzing_inventory"))

        inventory.retrieve(
            optimizer.ingredients_data.keys(),
            min_id=args.min, max_id=args.max, refresh=args.refresh,
        )

        if args.delete_old:
            deleted = inventory.delete_processed_screenshots()
            print(translate("screenshots_deleted", count=len(deleted)))

        execute(inventory.ingredients, optimizer)


if __name__ == "__main__":
    main()
