"""UESP Skyrim wiki scraping: ingredients and alchemy effects data."""
from app.scraping._effects import get_effects_data
from app.scraping._ingredients import get_ingredients_data

__all__ = ["get_effects_data", "get_ingredients_data"]
