"""
Base obfuscated model implementation.

This module provides the foundation for database models with field obfuscation,
allowing transparent mapping between semantic field names and UUIDs.
"""

import os
from enum import Enum
from typing import TypeVar, cast, get_type_hints
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

from ..config import DBFacadeConfig
from ..registry.client import RegistryClient


class ObfuscationLevel(Enum):
    """Enum defining the level of obfuscation to apply to a field."""
    
    # Field is obfuscated with UUID but not encrypted
    UUID_ONLY = "uuid_only"
    
    # Field is obfuscated with UUID and encrypted
    ENCRYPTED = "encrypted"
    
    # Field is not obfuscated, used for metadata or internal fields
    NONE = "none"


class ObfuscatedField:
    """
    Field descriptor for obfuscated fields.
    
    This descriptor allows customizing how individual fields are handled,
    including obfuscation level and encryption settings.
    """
    
    def __init__(
        self,
        *,
        obfuscation_level: ObfuscationLevel = ObfuscationLevel.UUID_ONLY,
        description: str | None = None,
    ) -> None:
        """
        Initialize an ObfuscatedField.
        
        Args:
            obfuscation_level: The level of obfuscation to apply to this field
            description: Optional description of the field (used for documentation)
        """
        self.obfuscation_level = obfuscation_level
        self.description = description
        self.field_name: str | None = None
        
    def __set_name__(self, owner: type["ObfuscatedModel"], name: str) -> None:
        """
        Store the field name when the descriptor is assigned to a class.
        
        Args:
            owner: The class that owns this descriptor
            name: The name of the descriptor in the class
        """
        self.field_name = name


T = TypeVar("T", bound="ObfuscatedModel")


class ObfuscatedModel(BaseModel):
    """
    Base class for models with automatic field obfuscation.
    
    This class provides the foundation for defining Pydantic models that
    automatically map between semantic field names and UUIDs using the
    registry service.
    """
    
    # Allow arbitrary types to support UUID fields and custom types
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Class variable to store field metadata for obfuscation
    __obfuscated_fields__: dict[str, ObfuscatedField] = {}
    
    # Registry client instance for this model
    __registry_client: RegistryClient | None = None
    
    @classmethod
    def _get_registry_client(cls) -> RegistryClient:
        """
        Get or create the registry client instance.
        
        Returns:
            The registry client instance for this model
        """
        if cls.__registry_client is None:
            # Create a new registry client
            cls.__registry_client = RegistryClient()
        
        return cls.__registry_client
    
    @classmethod
    def _collect_obfuscated_fields(cls) -> dict[str, ObfuscatedField]:
        """
        Collect all ObfuscatedField descriptors from the class.
        
        Returns:
            Dictionary mapping field names to their ObfuscatedField instance
        """
        fields: dict[str, ObfuscatedField] = {}
        
        # Look through all class attributes
        for name, value in cls.__dict__.items():
            if isinstance(value, ObfuscatedField):
                fields[name] = value
        
        # Store the result in the class for future use
        cls.__obfuscated_fields__ = fields
        return fields
    
    @classmethod
    def _register_model_schema(cls) -> dict[str, UUID]:
        """
        Register this model's schema with the registry service.
        
        This ensures that all field names have corresponding UUIDs
        registered in the registry service.
        
        Returns:
            Dictionary mapping field names to their UUID
        """
        # Get the registry client
        registry = cls._get_registry_client()
        
        # Collect all field names that need obfuscation
        fields = cls._collect_obfuscated_fields()
        field_names = set(fields.keys())
        
        # Add any fields defined using type annotations but not ObfuscatedField
        hints = get_type_hints(cls)
        for name in hints:
            # Skip private attributes
            if name.startswith("_") or name in field_names:
                continue
            
            # Add to the set of fields to register
            field_names.add(name)
        
        # Register all fields with the registry
        mapping: dict[str, UUID] = {}
        for name in field_names:
            uuid = registry.get_uuid_for_label(name)
            mapping[name] = uuid
        
        # Also register the model class name itself
        model_name = cls.__name__
        model_uuid = registry.get_uuid_for_label(model_name)
        mapping[model_name] = model_uuid
        
        return mapping
    
    def _map_to_uuids(self, data: dict[str, object]) -> dict[str, object]:
        """
        Map semantic field names to UUIDs and encrypt sensitive fields.
        
        This converts a dictionary with semantic keys to one with UUID keys,
        ready for storing in the database. It also encrypts fields marked for
        encryption.
        
        Args:
            data: Dictionary with semantic field names as keys
            
        Returns:
            Dictionary with UUID keys and encrypted sensitive fields
        """
        # Get the registry client
        registry = self._get_registry_client()
        
        # Check if encryption is enabled
        encryption_enabled = DBFacadeConfig.is_encryption_enabled()
        
        # If encryption is enabled, create an encryptor
        encryptor = None
        if encryption_enabled:
            from ..encryption import FieldEncryptor
            encryptor = FieldEncryptor()
        
        # Create a new dictionary with UUID keys
        uuid_data: dict[str, object] = {}
        
        # Get the obfuscated field metadata
        obfuscated_fields = self._collect_obfuscated_fields()
        
        # Convert each key to its UUID
        for key, value in data.items():
            # Skip private attributes
            if key.startswith("_"):
                uuid_data[key] = value
                continue
            
            # Get the UUID for this field
            try:
                uuid_obj = registry.get_uuid_for_label(key)
                uuid_key = str(uuid_obj)  # Use string representation for storage
                
                # Check if this field should be encrypted
                should_encrypt = (
                    encryption_enabled and
                    encryptor is not None and
                    key in obfuscated_fields and
                    obfuscated_fields[key].obfuscation_level.value == "encrypted"
                )
                
                # Handle datetime serialization
                if hasattr(value, 'isoformat'):  # datetime objects
                    value = value.isoformat()
                
                if should_encrypt:
                    # Encrypt the field value
                    encrypted_value = encryptor.encrypt_field(value, uuid_obj)
                    uuid_data[uuid_key] = encrypted_value
                else:
                    # Store the value as-is
                    uuid_data[uuid_key] = value
            except Exception:
                # In dev mode, allow using semantic names for convenience
                if DBFacadeConfig.is_dev_mode():
                    # Also handle datetime serialization in dev mode
                    if hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    uuid_data[key] = value
                else:
                    # In production, fail hard if a mapping is missing
                    raise
        
        return uuid_data
    
    def _map_to_semantic(self, data: dict[str, object]) -> dict[str, object]:
        """
        Map UUID field names back to semantic names and decrypt encrypted fields.
        
        This converts a dictionary with UUID keys to one with semantic keys,
        for use in development environments. It also decrypts any encrypted fields.
        
        Args:
            data: Dictionary with UUID keys
            
        Returns:
            Dictionary with semantic field names as keys and decrypted values
        """
        # Only perform semantic mapping in development mode
        if not DBFacadeConfig.is_dev_mode():
            return data
        
        # Get the registry client
        registry = self._get_registry_client()
        
        # Check if encryption is enabled
        encryption_enabled = DBFacadeConfig.is_encryption_enabled()
        
        # If encryption is enabled, create an encryptor
        encryptor = None
        if encryption_enabled:
            from ..encryption import FieldEncryptor
            encryptor = FieldEncryptor()
        
        # Create a new dictionary with semantic keys
        semantic_data: dict[str, object] = {}
        
        # Convert each UUID key to its semantic name
        for key, value in data.items():
            # Skip private attributes
            if key.startswith("_"):
                semantic_data[key] = value
                continue
            
            # Try to parse the key as a UUID
            try:
                uuid_obj = UUID(key)
                label = registry.get_label_for_uuid(uuid_obj)
                
                # Check if this might be an encrypted value
                is_encrypted = (
                    encryption_enabled and
                    encryptor is not None and
                    isinstance(value, dict) and
                    "value" in value and
                    "metadata" in value
                )
                
                if is_encrypted:
                    # Attempt to decrypt the value
                    try:
                        decrypted_value = encryptor.decrypt_field(value, uuid_obj)
                        semantic_data[label] = decrypted_value
                    except Exception:
                        # If decryption fails, use the raw value
                        semantic_data[label] = value
                else:
                    # Use the raw value
                    semantic_data[label] = value
            except (ValueError, KeyError):
                # If not a valid UUID or not found, keep the original key
                semantic_data[key] = value
        
        return semantic_data
    
    def get_obfuscated_data(self) -> dict[str, object]:
        """
        Get the obfuscated representation of this model.
        
        This method converts semantic field names to UUIDs and optionally
        encrypts sensitive fields before storing in the database.
        
        Returns:
            Dictionary with UUID keys and possibly encrypted values
        """
        # Get a dictionary representation of the model
        data = self.model_dump()
        
        # Map semantic names to UUIDs
        return self._map_to_uuids(data)

    def model_dump(self, **kwargs: object) -> dict[str, object]:
        """
        Override model_dump to map UUIDs back to semantic names in dev mode.
        
        Args:
            **kwargs: Keyword arguments to pass to the parent method
            
        Returns:
            Dictionary representation of the model with appropriate keys
        """
        # Get the raw dictionary from the parent method
        uuid_dict = super().model_dump(**kwargs)
        
        # In development mode, map UUIDs back to semantic names
        if DBFacadeConfig.is_dev_mode():
            return self._map_to_semantic(uuid_dict)
        
        return uuid_dict
    
    @classmethod
    def create_from_semantic(cls: type[T], **data: object) -> T:
        """
        Create a model instance from semantic field names.
        
        This is a convenience method for creating a model instance with
        semantic field names, which will be automatically mapped to UUIDs.
        
        Args:
            **data: Keyword arguments with semantic field names
            
        Returns:
            A new model instance
        """
        # Map semantic field names to UUIDs
        registry = cls._get_registry_client()
        uuid_data: dict[str, object] = {}
        
        for key, value in data.items():
            # Skip private attributes
            if key.startswith("_"):
                uuid_data[key] = value
                continue
            
            # Get the UUID for this field
            try:
                uuid = registry.get_uuid_for_label(key)
                uuid_key = str(uuid)
                
                # Handle datetime serialization
                if hasattr(value, 'isoformat'):  # datetime objects
                    value = value.isoformat()
                    
                uuid_data[uuid_key] = value
            except Exception:
                # In dev mode, allow using semantic names for convenience
                if DBFacadeConfig.is_dev_mode():
                    # Also handle datetime serialization in dev mode
                    if hasattr(value, 'isoformat'):
                        value = value.isoformat()
                    uuid_data[key] = value
                else:
                    # In production, fail hard if a mapping is missing
                    raise
        
        # Create the model instance with UUID keys
        return cls(**uuid_data)
    
    @classmethod
    def create_from_uuid(cls: type[T], **data: object) -> T:
        """
        Create a model instance from UUID field names.
        
        This method creates a model instance directly from database data
        with UUID keys.
        
        Args:
            **data: Keyword arguments with UUID field names
            
        Returns:
            A new model instance
        """
        # Create the model instance with UUID keys
        return cls(**data)
    
    @classmethod
    def from_obfuscated(cls: type[T], data: dict[str, object]) -> T:
        """
        Create a model instance from obfuscated data.
        
        This method handles both UUID mapping and decryption if needed.
        
        Args:
            data: Dictionary with UUID keys and possibly encrypted values
            
        Returns:
            A new instance of the model with semantic field names
        """
        # In development mode, convert UUIDs back to semantic names
        if DBFacadeConfig.is_dev_mode():
            registry = cls._get_registry_client()
            semantic_data = {}
            
            for uuid_key, value in data.items():
                try:
                    # Try to parse as UUID and get the semantic label
                    uuid_obj = UUID(uuid_key)
                    label = registry.get_label_for_uuid(uuid_obj)
                    semantic_data[label] = value
                except (ValueError, KeyError):
                    # If not a valid UUID or not found, keep the original key
                    semantic_data[uuid_key] = value
            
            return cls(**semantic_data)
        else:
            # In production mode, use the UUID keys directly
            return cls(**data)