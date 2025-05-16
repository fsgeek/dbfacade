"""
DB Facade - A database obfuscation layer.

This package provides tools for obfuscating database fields and models,
mapping between semantic names and UUIDs to protect sensitive data.
"""

from .config import DBFacadeConfig
from .models import ObfuscatedModel, ObfuscatedField
from .encryption import FieldEncryptor, EncryptionMetadata, EncryptionAlgorithm

__version__ = "0.1.0"

__all__ = [
    "DBFacadeConfig", 
    "ObfuscatedModel", 
    "ObfuscatedField",
    "FieldEncryptor", 
    "EncryptionMetadata", 
    "EncryptionAlgorithm"
]