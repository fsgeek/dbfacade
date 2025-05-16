"""
Registry service integration for DB Facade.

This module provides integration with the registry service for mapping
between semantic labels and UUIDs.
"""

from .client import RegistryClient

__all__ = ["RegistryClient"]