"""
Registry client for mapping semantic labels to UUIDs.

This module provides a client for interacting with the registry service,
which maintains mappings between semantic labels and UUIDs.
"""

import time
from typing import Dict, Optional, Set, Tuple, Type, Union
from uuid import UUID, uuid4

import requests

from ..config import DBFacadeConfig


class RegistryClient:
    """
    Client for interacting with the registry service.
    
    This client provides methods for looking up UUIDs by semantic label
    and vice versa, as well as for registering new mappings.
    """
    
    def __init__(self, base_url: Optional[str] = None) -> None:
        """
        Initialize the registry client.
        
        Args:
            base_url: Optional base URL for the registry service
        """
        self.base_url = base_url or DBFacadeConfig.get_registry_url()
        
        # Cache for mapping lookups to reduce registry service calls
        self._label_to_uuid_cache: Dict[str, Tuple[UUID, float]] = {}
        self._uuid_to_label_cache: Dict[UUID, Tuple[str, float]] = {}
        
        # Cache TTL in seconds
        self._cache_ttl = DBFacadeConfig.get("registry.cache_ttl", 3600)
    
    def get_uuid_for_label(self, label: str) -> UUID:
        """
        Get the UUID for a semantic label.
        
        If the label is not already registered, a new UUID will be
        generated and registered for it.
        
        Args:
            label: The semantic label to look up
            
        Returns:
            The UUID for the label
            
        Raises:
            ValueError: If the label is invalid
            ConnectionError: If the registry service is unavailable
        """
        # Check the cache first
        if label in self._label_to_uuid_cache:
            uuid_value, timestamp = self._label_to_uuid_cache[label]
            if time.time() - timestamp < self._cache_ttl:
                return uuid_value
        
        # Use the ArangoDB client to get or create the UUID
        try:
            from ..db.arangodb import ArangoDBClient
            db = ArangoDBClient()
            uuid_value = db.get_uuid_for_label(label)
        except ImportError as e:
            # Specific error for import failure
            raise ConnectionError(f"Registry client unavailable: {e}")
        # No generic exception handler - let errors propagate upward for better debugging
        
        # Store in cache
        self._label_to_uuid_cache[label] = (uuid_value, time.time())
        self._uuid_to_label_cache[uuid_value] = (label, time.time())
        
        return uuid_value
    
    def get_label_for_uuid(self, uuid: UUID) -> str:
        """
        Get the semantic label for a UUID.
        
        Args:
            uuid: The UUID to look up
            
        Returns:
            The semantic label for the UUID
            
        Raises:
            KeyError: If the UUID is not registered
            ConnectionError: If the registry service is unavailable
        """
        # Check the cache first
        if uuid in self._uuid_to_label_cache:
            label, timestamp = self._uuid_to_label_cache[uuid]
            if time.time() - timestamp < self._cache_ttl:
                return label
        
        # Use the ArangoDB client to get the label
        try:
            from ..db.arangodb import ArangoDBClient
            db = ArangoDBClient()
            label = db.get_label_for_uuid(uuid)
        except ImportError as e:
            # Specific error for import failure
            raise ConnectionError(f"Registry client unavailable: {e}")
        # No generic exception handler - let errors propagate upward for better debugging
        
        # Store in cache
        self._uuid_to_label_cache[uuid] = (label, time.time())
        self._label_to_uuid_cache[label] = (uuid, time.time())
        
        return label
    
    def register_model_schema(self, model_class: Type) -> Dict[str, UUID]:
        """
        Register all fields in a model class with the registry.
        
        This ensures that all fields in the model have UUIDs assigned
        in the registry service.
        
        Args:
            model_class: The model class to register
            
        Returns:
            Dictionary mapping field names to their UUIDs
            
        Raises:
            ConnectionError: If the registry service is unavailable
        """
        # Get all field names from the model
        field_names: Set[str] = set()
        
        # Look for field attributes on the model class
        for name, value in model_class.__annotations__.items():
            # Skip private attributes
            if not name.startswith("_"):
                field_names.add(name)
        
        # Register each field
        mapping: Dict[str, UUID] = {}
        for name in field_names:
            mapping[name] = self.get_uuid_for_label(name)
        
        # Also register the model class name itself
        model_name = model_class.__name__
        mapping[model_name] = self.get_uuid_for_label(model_name)
        
        return mapping