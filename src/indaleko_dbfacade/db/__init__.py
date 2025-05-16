"""
Database integration for DB Facade.

This module provides database clients for connecting to various
database backends, with current support for ArangoDB.
"""

from .arangodb import ArangoDBClient

__all__ = ["ArangoDBClient"]