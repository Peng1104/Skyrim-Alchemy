"""Test script - CLI run without spinning up the API server."""
import argparse
from collections.abc import Iterable

from app.config import get_settings
from app.i18n import translate
from app.inventory import Inventory
from app.logger import ConsoleCapture
from app.optimizer import AlchemyOptimizer, execute


def _parse_id_range(part: str) -> range:
    """
    Parse a single inclusive range selector part (e.g. "0-5") into a `range`.

    Parameters
    ----------
    part : str
        The range part, containing a "-".

    Returns
    -------
    range
        The inclusive ID range it describes.

    Raises
    ------
    argparse.ArgumentTypeError
        If `part` isn't a valid range.
    """
    start_str, _, end_str = part.partition("-")

    try:
        start, end = int(start_str), int(end_str)
    except ValueError:
        raise argparse.ArgumentTypeError(translate("cli_error_invalid_range", part=part)) from None

    if start > end:
        raise argparse.ArgumentTypeError(translate("cli_error_invalid_range_order", part=part))

    return range(start, end + 1)


def _parse_id_part(part: str) -> Iterable[int]:
    """
    Parse one comma-separated selector part into the screenshot IDs it represents.

    Parameters
    ----------
    part : str
        A single non-empty, stripped part (a range like "0-5", or a single ID).

    Returns
    -------
    Iterable[int]
        The ID(s) this part represents.

    Raises
    ------
    argparse.ArgumentTypeError
        If `part` isn't a valid range or ID.
    """
    if "-" in part:
        return _parse_id_range(part)

    try:
        return (int(part),)
    except ValueError:
        raise argparse.ArgumentTypeError(
            translate("cli_error_invalid_screenshot_id", part=part)
        ) from None


def _parse_id_selector(spec: str) -> list[int]:
    """
    Parse a screenshot ID selector into a sorted list of unique IDs.

    Accepts a comma-separated combination of single IDs and inclusive
    ranges, e.g. "2" -> [2], "0-5" -> [0,1,2,3,4,5], "0,2,4" -> [0,2,4],
    "0-2,4,6-8" -> [0,1,2,4,6,7,8].

    Parameters
    ----------
    spec : str
        The selector string.

    Returns
    -------
    list[int]
        Sorted unique screenshot IDs.

    Raises
    ------
    argparse.ArgumentTypeError
        If `spec` isn't a valid selector.
    """
    ids: set[int] = set()

    for part in spec.split(","):
        part = part.strip()

        if part:
            ids.update(_parse_id_part(part))

    if not ids:
        raise argparse.ArgumentTypeError(translate("cli_error_no_ids_given"))

    return sorted(ids)


def _add_id_selector_argument(parser: argparse.ArgumentParser, *flags: str, help: str) -> None:
    """
    Add a CLI flag that takes an optional screenshot ID selector.

    Given without a value, the flag resolves to an empty list - the "every
    known screenshot ID" sentinel every caller of this flag shares. Given
    with a value, `_parse_id_selector` parses it (a single ID, a range like
    0-5, or a comma-separated combination like 0,2,4-6).

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The parser to add the flag to.
    *flags : str
        The flag's option strings (e.g. "--info").
    help : str
        Help text specific to this flag - the shared selector syntax isn't
        repeated here, so keep it focused on what the flag does.
    """
    parser.add_argument(
        *flags, nargs="?", type=_parse_id_selector, const=[], default=None,
        metavar="IDS",
        help=f"{help} {translate('cli_help_id_selector_suffix')}",
    )


def _parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments (`min`, `max`, `refresh`, `delete_old`, `delete_cache`,
        `list`, `info`).
    """
    parser = argparse.ArgumentParser(description=translate("cli_description"))
    parser.add_argument(
        "--min", type=int, default=None,
        help=translate("cli_help_min"),
    )
    parser.add_argument(
        "--max", type=int, default=None,
        help=translate("cli_help_max"),
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help=translate("cli_help_refresh"),
    )
    _add_id_selector_argument(
        parser, "--delete-old",
        help=translate("cli_help_delete_old"),
    )
    _add_id_selector_argument(
        parser, "--delete-cache",
        help=translate("cli_help_delete_cache"),
    )
    parser.add_argument(
        "--list", action="store_true",
        help=translate("cli_help_list"),
    )
    _add_id_selector_argument(
        parser, "--info",
        help=translate("cli_help_info"),
    )

    args = parser.parse_args()

    if (args.min is None) != (args.max is None):
        parser.error(translate("cli_error_min_max_together"))

    return args


def _print_screenshot_list(inventory: Inventory) -> None:
    """
    Print every known screenshot's availability plus the marker/resolution ranges.

    Parameters
    ----------
    inventory : Inventory
        The Inventory to list screenshots for.
    """
    statuses = inventory.list_screenshots()

    if not statuses:
        print(translate("screenshot_list_empty"))
        return

    print(translate("screenshot_list_header"))

    for status in statuses:
        print(translate(
            "screenshot_list_line",
            id=status.id,
            image_mark="✔" if status.has_image else "✖",
            cache_mark="✔" if status.has_cache else "✖",
        ))

    marker_ids = inventory.marker_screenshot_ids()

    if marker_ids:
        print(translate("marker_range_line", min_id=min(marker_ids), max_id=max(marker_ids)))
    else:
        print(translate("marker_range_empty"))

    resolved = inventory.resolve_new_range()

    if resolved is not None:
        resolved_min, resolved_max = resolved
        print(translate("next_range_line", min_id=resolved_min, max_id=resolved_max))


def _resolve_id_selector(selector: list[int], inventory: Inventory) -> list[int]:
    """
    Expand an ID-selector CLI value into concrete screenshot IDs.

    An empty selector is `_add_id_selector_argument`'s "every known screenshot
    ID" sentinel (the flag was given without a value); a non-empty one is
    returned as-is.

    Parameters
    ----------
    selector : list[int]
        The parsed `--info`/`--delete-old`/`--delete-cache` value.
    inventory : Inventory
        The Inventory to list all known screenshot IDs from, when needed.

    Returns
    -------
    list[int]
        The concrete screenshot IDs to act on.
    """
    if selector:
        return selector

    return [status.id for status in inventory.list_screenshots()]


def _print_screenshot_info(inventory: Inventory, screenshot_ids: list[int]) -> None:
    """
    Print image/cache availability and cached ingredients for one or more screenshots.

    Parameters
    ----------
    inventory : Inventory
        The Inventory to look up the screenshots in.
    screenshot_ids : list[int]
        The screenshot IDs to show, in the order they should be printed.
    """
    for index, screenshot_id in enumerate(screenshot_ids):
        if index > 0:
            print()

        detail = inventory.screenshot_info(screenshot_id)

        print(translate("screenshot_info_header", id=detail.id))
        print(translate("screenshot_info_image_line", mark="✔" if detail.has_image else "✖"))
        print(translate("screenshot_info_cache_line", mark="✔" if detail.has_cache else "✖"))

        if not detail.ingredients:
            print(translate("screenshot_info_no_ingredients"))
            continue

        for ingredient in detail.ingredients:
            print(translate("ingredient_line", name=ingredient.name, amount=ingredient.amount))


def main() -> None:
    """Run the CLI: read the inventory (OCR or cache) and print the optimized recipes."""
    args = _parse_args()

    settings = get_settings()
    inventory = Inventory(settings.game_directory)

    if args.list:
        with ConsoleCapture():
            _print_screenshot_list(inventory)
        return

    if args.info is not None:
        with ConsoleCapture():
            _print_screenshot_info(inventory, _resolve_id_selector(args.info, inventory))
        return

    if args.delete_old is not None or args.delete_cache is not None:
        # Standalone maintenance action, like --list/--info above - neither
        # deletion depends on retrieve() having run first (both work purely
        # off what's already on disk/cached from prior runs), so this must
        # not fall through to combining screenshots and printing the full
        # optimization result the caller didn't ask for.
        with ConsoleCapture():
            if args.delete_old is not None:
                deleted = inventory.delete_processed_screenshots(
                    _resolve_id_selector(args.delete_old, inventory)
                )
                print(translate("screenshots_deleted", count=len(deleted)))

            if args.delete_cache is not None:
                deleted_ids = inventory.delete_cached_screenshots(
                    _resolve_id_selector(args.delete_cache, inventory)
                )
                print(translate("cache_deleted", count=len(deleted_ids)))
        return

    optimizer = AlchemyOptimizer(decimal_places=3)

    with ConsoleCapture():
        print(translate("analyzing_inventory"))

        min_id = args.min
        max_id = args.max

        # min/max are enforced as a pair by _parse_args, so either both are set
        # (explicit range) or both are None (resolve automatically). See
        # Inventory.resolve_new_range for exactly how the range is picked.
        if min_id is None:
            resolved = inventory.resolve_new_range()

            if resolved is not None:
                min_id, max_id = resolved

        inventory.retrieve(
            optimizer.ingredients_data.keys(),
            min_id=min_id, max_id=max_id, refresh=args.refresh,
        )

        execute(inventory.ingredients, optimizer)


if __name__ == "__main__":
    main()
