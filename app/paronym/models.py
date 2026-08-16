"""Backward-compatible imports for the former paronym model module."""

from app.models import Paronym, ParonymGroup, Sentence

__all__ = ["Paronym", "ParonymGroup", "Sentence"]
