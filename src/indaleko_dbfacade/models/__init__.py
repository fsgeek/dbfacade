"""
Base model interfaces for DB Facade.

This module provides the core model classes for working with obfuscated database fields.
"""

from .obfuscated_model import ObfuscatedModel, ObfuscatedField

__all__ = ["ObfuscatedModel", "ObfuscatedField"]