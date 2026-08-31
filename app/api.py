"""FastAPI application exposing the Skyrim alchemy optimizer as a service."""
from functools import lru_cache

from fastapi import FastAPI

from app.cache import clear_pages_cache
from app.config import get_settings
from app.inventory import Inventory
from app.models import OptimizationResult
from app.optimizer import AlchemyOptimizer

app = FastAPI(title="Skyrim Alchemy Optimizer")


@lru_cache
def get_optimizer() -> AlchemyOptimizer:
    """
    Get the cached optimizer instance, loading ingredient/effect data once per process.

    Returns
    -------
    AlchemyOptimizer
        The cached optimizer instance.
    """
    return AlchemyOptimizer(decimal_places=3)


@app.get("/health")
def health() -> dict[str, str]:
    """
    Perform a liveness/readiness check.

    Returns
    -------
    dict[str, str]
        Status payload.
    """
    return {"status": "ok"}


@app.delete("/cache/pages")
def clear_cache() -> dict[str, int]:
    """
    Delete every cached UESP HTML page and drop the in-memory optimizer.

    The next `/optimize` call will re-scrape ingredients/effects/priority
    data from scratch instead of reusing stale cached pages.

    Returns
    -------
    dict[str, int]
        Number of HTML files deleted.
    """
    deleted = clear_pages_cache()
    get_optimizer.cache_clear()

    return {"deleted": deleted}


@app.post("/optimize")
def optimize() -> OptimizationResult:
    """
    Read the current inventory and return the optimal potion fabrication sequence.

    Returns
    -------
    OptimizationResult
        The optimal fabrication sequence and remaining ingredients.
    """
    settings = get_settings()
    optimizer = get_optimizer()

    inventory = Inventory(settings.game_directory)
    inventory.retrieve(optimizer.ingredients_data.keys())

    return optimizer.run_optimization(inventory.ingredients)
