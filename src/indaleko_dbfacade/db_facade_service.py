# db_facade_service.py — Semantic DB Façade Service

"""
This module defines a semantic-safe database interface for the Indaleko DB Façade.

It enforces UUID-based access patterns, uses the registry as the only source of semantic resolution,
and supports a developer-mode overlay for introspection.

This service layer sits between application code and the database, providing a clean interface
for obfuscated database operations with proper error handling following the fail-stop design principle.
"""

import sys
import uuid
from datetime import datetime, timezone
from typing import TypeVar, cast

from pydantic import BaseModel

from .config import DBFacadeConfig
from .db.arangodb import ArangoDBClient
from .registry.client import RegistryClient
from .models.obfuscated_model import ObfuscatedModel


T = TypeVar('T', bound=BaseModel)


class DBFacadeService:
    """
    Main service class for the Indaleko DB Façade.
    
    This service provides methods for interacting with the database using
    obfuscated field names, with support for development mode to show
    semantic field names for easier debugging.
    
    All database operations are performed through this service, which
    handles the mapping between UUIDs and semantic field names.
    """
    
    def __init__(
        self,
        registry_collection: str = "dbfacade_registry",
        data_collection: str = "dbfacade_data"
    ) -> None:
        """
        Initialize the DB Façade Service.
        
        Args:
            registry_collection: Name of the collection for registry data
            data_collection: Name of the collection for application data
        """
        # Initialize database client
        try:
            self.db = ArangoDBClient(
                registry_collection=registry_collection,
                data_collection=data_collection
            )
        except Exception as e:
            print(f"CRITICAL: Failed to initialize database connection: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Initialize registry client
        try:
            self.registry = RegistryClient()
        except Exception as e:
            print(f"CRITICAL: Failed to initialize registry client: {e}", file=sys.stderr)
            sys.exit(1)
    
    def store_model(self, model: ObfuscatedModel) -> uuid.UUID:
        """
        Store an obfuscated model in the database.
        
        This method converts the model to its obfuscated form and
        stores it in the database.
        
        Args:
            model: The model to store
            
        Returns:
            UUID of the stored record
            
        Raises:
            ValueError: If the model is invalid
        """
        if not isinstance(model, ObfuscatedModel):
            raise ValueError("Model must be an instance of ObfuscatedModel")
        
        # Get the collection UUID for the model
        collection_name = model.__class__.__name__
        collection_uuid = self.registry.get_uuid_for_label(collection_name)
        
        # Get the obfuscated data
        obfuscated_data = model.get_obfuscated_data()
        
        # Store the data in the database
        record_uuid = self.db.insert(collection_uuid, obfuscated_data)
        
        return record_uuid
    
    def get_model(
        self, 
        model_class: type[T], 
        record_uuid: uuid.UUID, 
        dev_mode: bool | None = None
    ) -> T:
        """
        Get a model from the database.
        
        This method retrieves a record from the database and converts it
        back to a model instance.
        
        Args:
            model_class: The model class to instantiate
            record_uuid: UUID of the record to retrieve
            dev_mode: Override for development mode
            
        Returns:
            Instance of the model class
            
        Raises:
            ValueError: If the record is not found
            TypeError: If the model class is not a subclass of ObfuscatedModel
        """
        if not issubclass(model_class, ObfuscatedModel):
            raise TypeError("Model class must be a subclass of ObfuscatedModel")
        
        # Get the collection UUID for the model class
        collection_name = model_class.__name__
        collection_uuid = self.registry.get_uuid_for_label(collection_name)
        
        # Use the provided dev_mode if specified, otherwise use the config
        use_dev_mode = dev_mode if dev_mode is not None else DBFacadeConfig.is_dev_mode()
        
        try:
            # Get the record from the database
            data = self.db.get(collection_uuid, record_uuid)
            
            # Convert the data back to a model instance
            if use_dev_mode:
                # In development mode, resolve UUIDs to semantic field names
                resolved_data = {}
                for field_uuid, value in data.items():
                    try:
                        field_name = self.registry.get_label_for_uuid(uuid.UUID(field_uuid))
                        resolved_data[field_name] = value
                    except (ValueError, KeyError):
                        # If we can't resolve the UUID, use it as is
                        resolved_data[field_uuid] = value
                
                return model_class.parse_obj(resolved_data)
            else:
                # In production mode, use the model's from_obfuscated method
                return model_class.from_obfuscated(data)
        except ValueError as e:
            # Re-raise with a more descriptive message
            raise ValueError(f"Record not found: {e}")
    
    def query_models(
        self,
        model_class: type[T],
        filter_dict: dict[str, object],
        limit: int = 50,
        dev_mode: bool | None = None
    ) -> list[T]:
        """
        Query models from the database.
        
        This method queries records from the database and converts them
        back to model instances.
        
        Args:
            model_class: The model class to instantiate
            filter_dict: Filter criteria (can use semantic field names in dev mode)
            limit: Maximum number of results to return
            dev_mode: Override for development mode
            
        Returns:
            List of model instances
            
        Raises:
            TypeError: If the model class is not a subclass of ObfuscatedModel
        """
        if not issubclass(model_class, ObfuscatedModel):
            raise TypeError("Model class must be a subclass of ObfuscatedModel")
        
        # Get the collection UUID for the model class
        collection_name = model_class.__name__
        collection_uuid = self.registry.get_uuid_for_label(collection_name)
        
        # Use the provided dev_mode if specified, otherwise use the config
        use_dev_mode = dev_mode if dev_mode is not None else DBFacadeConfig.is_dev_mode()
        
        # Convert filter criteria to use UUIDs
        obfuscated_filter = {}
        for field_name, value in filter_dict.items():
            if use_dev_mode:
                # In development mode, convert semantic field names to UUIDs
                try:
                    field_uuid = self.registry.get_uuid_for_label(field_name)
                    obfuscated_filter[str(field_uuid)] = value
                except (ValueError, KeyError):
                    # If we can't resolve the field name, use it as is
                    obfuscated_filter[field_name] = value
            else:
                # In production mode, assume filter_dict already uses UUIDs
                obfuscated_filter[field_name] = value
        
        # Query the database
        results = self.db.query(collection_uuid, obfuscated_filter, limit)
        
        # Convert the results to model instances
        models = []
        for data in results:
            if use_dev_mode:
                # In development mode, resolve UUIDs to semantic field names
                resolved_data = {}
                for field_uuid, value in data.items():
                    try:
                        field_name = self.registry.get_label_for_uuid(uuid.UUID(field_uuid))
                        resolved_data[field_name] = value
                    except (ValueError, KeyError):
                        # If we can't resolve the UUID, use it as is
                        resolved_data[field_uuid] = value
                
                models.append(model_class.parse_obj(resolved_data))
            else:
                # In production mode, use the model's from_obfuscated method
                models.append(model_class.from_obfuscated(data))
        
        return models
    
    def update_model(self, model: ObfuscatedModel, record_uuid: uuid.UUID) -> None:
        """
        Update a model in the database.
        
        This method converts the model to its obfuscated form and
        updates the corresponding record in the database.
        
        Args:
            model: The updated model
            record_uuid: UUID of the record to update
            
        Raises:
            ValueError: If the model is invalid or the record is not found
        """
        if not isinstance(model, ObfuscatedModel):
            raise ValueError("Model must be an instance of ObfuscatedModel")
        
        # Get the collection UUID for the model
        collection_name = model.__class__.__name__
        collection_uuid = self.registry.get_uuid_for_label(collection_name)
        
        # Get the obfuscated data
        obfuscated_data = model.get_obfuscated_data()
        
        # Update the record in the database
        self.db.update(collection_uuid, record_uuid, obfuscated_data)
    
    def delete_model(self, model_class: type[ObfuscatedModel], record_uuid: uuid.UUID) -> None:
        """
        Delete a model from the database.
        
        Args:
            model_class: The model class
            record_uuid: UUID of the record to delete
            
        Raises:
            TypeError: If the model class is not a subclass of ObfuscatedModel
        """
        if not issubclass(model_class, ObfuscatedModel):
            raise TypeError("Model class must be a subclass of ObfuscatedModel")
        
        # Get the collection UUID for the model class
        collection_name = model_class.__name__
        collection_uuid = self.registry.get_uuid_for_label(collection_name)
        
        # Delete the record from the database
        self.db.delete(collection_uuid, record_uuid)
    
    def resolve_uuid_fields(self, data: dict[str, object]) -> dict[str, str]:
        """
        Resolve UUID fields to their semantic names.
        
        This is a helper method for development mode, to make
        debugging easier.
        
        Args:
            data: Dictionary with UUID keys
            
        Returns:
            Dictionary mapping UUIDs to semantic names
        """
        resolved_fields = {}
        for field_uuid in data.keys():
            try:
                field_name = self.registry.get_label_for_uuid(uuid.UUID(field_uuid))
                resolved_fields[field_uuid] = field_name
            except (ValueError, KeyError):
                # If we can't resolve the UUID, skip it
                pass
        
        return resolved_fields
    
    def register_model_schema(self, model_class: type[ObfuscatedModel]) -> dict[str, uuid.UUID]:
        """
        Register a model schema with the registry.
        
        This ensures that all fields in the model have UUIDs assigned
        in the registry.
        
        Args:
            model_class: The model class to register
            
        Returns:
            Dictionary mapping field names to their UUIDs
        """
        return self.registry.register_model_schema(model_class)
