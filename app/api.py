"""FastAPI application exposing the Skyrim alchemy optimizer as a service."""
from functools import lru_cache
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.cache import clear_pages_cache
from app.inventory import match_ocr_data
from app.models import InventoryIngredient, OptimizationResult
from app.ocr_client import OcrServiceError, run_remote_ocr
from app.optimizer import AlchemyOptimizer
from app.perks import PerkConfig
from app.upload_validation import validate_upload_batch

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

    The next `/optimize/screenshots` call will re-scrape ingredients/effects/
    priority data from scratch instead of reusing stale cached pages.

    Returns
    -------
    dict[str, int]
        Number of HTML files deleted.
    """
    deleted = clear_pages_cache()
    get_optimizer.cache_clear()

    return {"deleted": deleted}


@app.post("/optimize/screenshots")
async def optimize_screenshots(
    files: Annotated[
        list[UploadFile],
        File(description="One or more Skyrim inventory screenshots (PNG only)."),
    ],
    perk_physician: Annotated[bool, Form()] = False,
    perk_benefactor: Annotated[bool, Form()] = False,
    perk_poisoner: Annotated[bool, Form()] = False,
    perk_purity: Annotated[bool, Form()] = False,
) -> OptimizationResult:
    """
    OCR one or more uploaded inventory screenshots and return the optimal fabrication sequence.

    Tesseract never runs in this process - each uploaded file's bytes are
    validated here (magic bytes, size, count) and then forwarded to the
    isolated `ocr` service over the internal Docker network. Perks are taken
    directly from this request, never from global settings, so concurrent
    requests with different perk selections never interfere with each other.

    Parameters
    ----------
    files : list[UploadFile]
        One or more screenshot images. When an inventory spans multiple
        scrolled screenshots, later files' readings for a given ingredient
        name overwrite earlier ones (each screenshot shows the current total
        amount, not a delta) - mirroring `Inventory.retrieve`'s merge rule.
    perk_physician : bool, optional
        Whether the Physician perk is active, by default False.
    perk_benefactor : bool, optional
        Whether the Benefactor perk is active, by default False.
    perk_poisoner : bool, optional
        Whether the Poisoner perk is active, by default False.
    perk_purity : bool, optional
        Whether the Purity perk is active, by default False.

    Returns
    -------
    OptimizationResult
        The optimal fabrication sequence and remaining ingredients.
    """
    if not files:
        raise HTTPException(400, detail="No files uploaded.")

    error = validate_upload_batch(files)
    if error is not None:
        status_code = 413 if error.reason == "too_large" else 400
        raise HTTPException(
            status_code, detail={"filename": error.filename, "reason": error.reason}
        )

    optimizer = get_optimizer()
    known_names = list(optimizer.ingredients_data.keys())
    known_effect_names = frozenset(name.lower() for name in optimizer.effects_data.keys())
    combined: dict[str, InventoryIngredient] = {}

    for upload in files:
        contents = await upload.read()

        try:
            data = run_remote_ocr(contents, upload.filename or "upload.png")
        except OcrServiceError as ocr_error:
            raise HTTPException(502, detail=str(ocr_error)) from None

        for ingredient in match_ocr_data(data, known_names, known_effect_names):
            combined[ingredient.name] = ingredient

    ingredients = sorted(combined.values(), key=lambda ingredient: ingredient.name)
    perks = PerkConfig(
        physician=perk_physician,
        benefactor=perk_benefactor,
        poisoner=perk_poisoner,
        purity=perk_purity,
    )

    return optimizer.run_optimization(ingredients, perks)
