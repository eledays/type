"""Normalization shared by exercise storage and analytics search."""

from __future__ import annotations


def normalize_exercise_search(value: str, *, keep_blank: bool = True) -> str:
    """Normalize searchable exercise text while optionally preserving blanks."""
    normalized = value.casefold().replace("ё", "е")
    return "".join(
        character
        for character in normalized
        if character.isalnum() or (keep_blank and character == "_")
    )
