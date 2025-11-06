"""Dataclasses and type helpers used across the project."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecipeConversionResult:
    formatted_recipe: str
    technical_title: str


__all__ = ["RecipeConversionResult"]
