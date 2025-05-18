"""
Registry client for mapping semantic labels to UUIDs.

This module provides a client for interacting with the registry service,
which maintains mappings between semantic labels and UUIDs.
"""

import sys
import time
from uuid import UUID, uuid4

from ..config import DBFacadeConfig


class RegistryClient:
    """
    Client for interacting with the registry service.
    
    This client provides methods for looking up UUIDs by semantic label
    and vice versa, as well as for registering new mappings.
    """
    
    def __init__(self, registry_collection: str = "dbfacade_registry", base_url: str | None = None) -> None:
        """
        Initialize the registry client.
        
        Args:
            registry_collection: Name of the registry collection
            base_url: Optional base URL for the registry service
        """
        self.base_url = base_url or DBFacadeConfig.get_registry_url()
        self.registry_collection_name = registry_collection
        
        # Cache for mapping lookups to reduce registry service calls
        self._label_to_uuid_cache: dict[str, tuple[UUID, float]] = {}
        self._uuid_to_label_cache: dict[UUID, tuple[str, float]] = {}
        
        # Cache TTL in seconds
        self._cache_ttl = DBFacadeConfig.get("registry.cache_ttl", 3600)
        
        # Initialize database connection for registry storage
        try:
            from ..db.arangodb import ArangoDBClient
            self.db = ArangoDBClient(registry_collection=registry_collection)
            # Use the registry collection from the database client
            self.registry_collection = self.db.db.collection(registry_collection)
        except Exception as e:
            print(f"Failed to initialize registry storage: {e}", file=sys.stderr)
            sys.exit(1)
    
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
        """
        # Check the cache first
        if label in self._label_to_uuid_cache:
            uuid_value, timestamp = self._label_to_uuid_cache[label]
            if time.time() - timestamp < self._cache_ttl:
                return uuid_value
        
        # Query the registry collection for the label
        try:
            # Look up the label in the registry
            query = """
            FOR doc IN dbfacade_registry
            FILTER doc.label == @label
            LIMIT 1
            RETURN doc
            """
            
            cursor = self.db.db.aql.execute(
                query,
                bind_vars={"label": label}
            )
            
            results = list(cursor)
            
            if results:
                # Label exists, get the UUID
                uuid_value = UUID(results[0]["uuid"])
            else:
                # Label doesn't exist, create a new mapping
                uuid_value = uuid4()
                document = {
                    "_key": str(uuid_value),
                    "label": label,
                    "uuid": str(uuid_value),
                    "created_at": time.time()
                }
                self.registry_collection.insert(document)
            
            # Update the caches
            self._label_to_uuid_cache[label] = (uuid_value, time.time())
            self._uuid_to_label_cache[uuid_value] = (label, time.time())
            
            return uuid_value
            
        except Exception as e:
            print(f"Failed to get UUID for label '{label}': {e}", file=sys.stderr)
            sys.exit(1)
    
    def get_label_for_uuid(self, uuid: UUID) -> str:
        """
        Get the semantic label for a UUID.
        
        Args:
            uuid: The UUID to look up
            
        Returns:
            The semantic label for the UUID
            
        Raises:
            KeyError: If the UUID is not found
        """
        # Check the cache first
        if uuid in self._uuid_to_label_cache:
            label, timestamp = self._uuid_to_label_cache[uuid]
            if time.time() - timestamp < self._cache_ttl:
                return label
        
        # Query the registry collection for the UUID
        try:
            # Look up the UUID in the registry
            query = """
            FOR doc IN dbfacade_registry
            FILTER doc.uuid == @uuid
            LIMIT 1
            RETURN doc
            """
            
            cursor = self.db.db.aql.execute(
                query,
                bind_vars={"uuid": str(uuid)}
            )
            
            results = list(cursor)
            
            if results:
                # UUID exists, get the label
                label = results[0]["label"]
                
                # Update the caches
                self._label_to_uuid_cache[label] = (uuid, time.time())
                self._uuid_to_label_cache[uuid] = (label, time.time())
                
                return label
            else:
                raise KeyError(f"UUID {uuid} not found in registry")
                
        except KeyError:
            raise
        except Exception as e:
            print(f"Failed to get label for UUID '{uuid}': {e}", file=sys.stderr)
            sys.exit(1)
    
    def register_model_schema(self, model_class: type) -> dict[str, UUID]:
        """
        Register a model schema and return the UUID mappings.
        
        Args:
            model_class: The model class to register
            
        Returns:
            Dictionary mapping field names to UUIDs
        """
        # Get the model's field names
        field_names = set()
        for name, field in model_class.__annotations__.items():
            if not name.startswith("_"):
                field_names.add(name)
        
        # Add the model class name itself
        field_names.add(model_class.__name__)
        
        # Register each field and build the mapping
        mapping = {}
        for name in field_names:
            mapping[name] = self.get_uuid_for_label(name)
        
        return mapping
    
    def clear_cache(self) -> None:
        """Clear the label/UUID caches."""
        self._label_to_uuid_cache.clear()
        self._uuid_to_label_cache.clear()