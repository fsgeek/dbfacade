"""
ArangoDB client for DB Facade.

This module provides a client for connecting to ArangoDB using
the MCP tools, designed for the DB Facade service.
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, cast

from ..config import DBFacadeConfig


class ArangoDBClient:
    """
    ArangoDB client for DB Facade.
    
    This client interacts with ArangoDB using the MCP tools, providing
    methods for CRUD operations on collections and documents.
    """
    
    def __init__(
        self, 
        registry_collection: str = "dbfacade_registry",
        data_collection: str = "dbfacade_data"
    ) -> None:
        """
        Initialize the ArangoDB client.
        
        Args:
            registry_collection: Name of the collection for registry data
            data_collection: Name of the collection for application data
        """
        self.registry_collection = registry_collection
        self.data_collection = data_collection
        
        # Import MCP tools
        # These are available at runtime but not during static analysis
        try:
            import builtins
            self.arango_query = getattr(builtins, "mcp__arango-mcp__arango_query")
            self.arango_insert = getattr(builtins, "mcp__arango-mcp__arango_insert")
            self.arango_update = getattr(builtins, "mcp__arango-mcp__arango_update")
            self.arango_remove = getattr(builtins, "mcp__arango-mcp__arango_remove")
            self.arango_create_collection = getattr(builtins, "mcp__arango-mcp__arango_create_collection")
            self.arango_list_collections = getattr(builtins, "mcp__arango-mcp__arango_list_collections")
        except (ImportError, AttributeError) as e:
            print(f"Failed to import MCP tools: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Verify collections exist
        self._ensure_collections_exist()
    
    def _ensure_collections_exist(self) -> None:
        """
        Ensure that the necessary collections exist in the database.
        
        If the collections don't exist, they will be created.
        """
        # List existing collections
        collections_result = self.arango_list_collections({})
        existing_collections = [col["name"] for col in collections_result]
        
        # Create registry collection if it doesn't exist
        if self.registry_collection not in existing_collections:
            print(f"Creating collection: {self.registry_collection}")
            self.arango_create_collection({"name": self.registry_collection})
            
        # Create data collection if it doesn't exist
        if self.data_collection not in existing_collections:
            print(f"Creating collection: {self.data_collection}")
            self.arango_create_collection({"name": self.data_collection})
    
    def insert(self, collection_uuid: uuid.UUID, data: Dict[str, Any]) -> uuid.UUID:
        """
        Insert a document into the database.
        
        Args:
            collection_uuid: UUID of the collection
            data: Document data with UUID keys
            
        Returns:
            UUID of the created document
        """
        # Generate a UUID for the document
        doc_uuid = uuid.uuid4()
        
        # Prepare the document for insertion
        document = {
            "_key": str(doc_uuid),
            "collection_uuid": str(collection_uuid),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "data": data
        }
        
        # Insert the document
        result = self.arango_insert({
            "collection": self.data_collection,
            "document": document
        })
        
        return doc_uuid
    
    def query(
        self, 
        collection_uuid: uuid.UUID, 
        filter_dict: Dict[str, Any],
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Query documents from the database.
        
        Args:
            collection_uuid: UUID of the collection
            filter_dict: Filter criteria with UUID keys
            limit: Maximum number of results to return
            
        Returns:
            List of matching documents
        """
        # Prepare the filter conditions
        filter_conditions = []
        bind_vars = {
            "collection_uuid": str(collection_uuid),
            "limit": limit
        }
        
        # Add filter conditions for each field
        for i, (field_uuid, value) in enumerate(filter_dict.items()):
            filter_conditions.append(f"doc.data['{field_uuid}'] == @value{i}")
            bind_vars[f"value{i}"] = value
        
        # Combine filter conditions
        filter_clause = " AND ".join(filter_conditions) if filter_conditions else "true"
        
        # Construct the AQL query
        query = f"""
        FOR doc IN {self.data_collection}
        FILTER doc.collection_uuid == @collection_uuid
        AND {filter_clause}
        LIMIT @limit
        RETURN doc
        """
        
        # Execute the query
        result = self.arango_query({
            "query": query,
            "bindVars": bind_vars
        })
        
        # Extract the data from each document
        return [doc["data"] for doc in result]
    
    def get(self, collection_uuid: uuid.UUID, record_uuid: uuid.UUID) -> Dict[str, Any]:
        """
        Get a document from the database.
        
        Args:
            collection_uuid: UUID of the collection
            record_uuid: UUID of the document
            
        Returns:
            Document data with UUID keys
        """
        # Construct the AQL query
        query = f"""
        FOR doc IN {self.data_collection}
        FILTER doc._key == @record_uuid
        AND doc.collection_uuid == @collection_uuid
        LIMIT 1
        RETURN doc
        """
        
        # Execute the query
        result = self.arango_query({
            "query": query,
            "bindVars": {
                "record_uuid": str(record_uuid),
                "collection_uuid": str(collection_uuid)
            }
        })
        
        # Check if a document was found
        if not result:
            raise ValueError(f"Document with UUID {record_uuid} not found")
            
        # Return the document data
        return result[0]["data"]
    
    def update(
        self, 
        collection_uuid: uuid.UUID, 
        record_uuid: uuid.UUID, 
        data: Dict[str, Any]
    ) -> None:
        """
        Update a document in the database.
        
        Args:
            collection_uuid: UUID of the collection
            record_uuid: UUID of the document
            data: Updated document data with UUID keys
        """
        # Prepare the update
        update_data = {
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Execute the update
        self.arango_update({
            "collection": self.data_collection,
            "key": str(record_uuid),
            "update": update_data
        })
    
    def delete(self, collection_uuid: uuid.UUID, record_uuid: uuid.UUID) -> None:
        """
        Delete a document from the database.
        
        Args:
            collection_uuid: UUID of the collection
            record_uuid: UUID of the document
        """
        # Execute the delete
        self.arango_remove({
            "collection": self.data_collection,
            "key": str(record_uuid)
        })
    
    def store_mapping(self, label: str, uuid_value: uuid.UUID) -> None:
        """
        Store a label to UUID mapping in the registry.
        
        Args:
            label: Semantic label
            uuid_value: Corresponding UUID
        """
        # Prepare the document
        document = {
            "_key": str(uuid_value),
            "label": label,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Check if the mapping already exists
        query = f"""
        FOR doc IN {self.registry_collection}
        FILTER doc._key == @uuid
        LIMIT 1
        RETURN doc
        """
        
        result = self.arango_query({
            "query": query,
            "bindVars": {
                "uuid": str(uuid_value)
            }
        })
        
        if result:
            # Update the existing mapping
            self.arango_update({
                "collection": self.registry_collection,
                "key": str(uuid_value),
                "update": {
                    "label": label,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            })
        else:
            # Insert a new mapping
            self.arango_insert({
                "collection": self.registry_collection,
                "document": document
            })
    
    def get_label_for_uuid(self, uuid_value: uuid.UUID) -> str:
        """
        Get the semantic label for a UUID.
        
        Args:
            uuid_value: UUID to look up
            
        Returns:
            Corresponding semantic label
            
        Raises:
            ValueError: If the UUID is not found in the registry
        """
        # Construct the AQL query
        query = f"""
        FOR doc IN {self.registry_collection}
        FILTER doc._key == @uuid
        LIMIT 1
        RETURN doc
        """
        
        # Execute the query
        result = self.arango_query({
            "query": query,
            "bindVars": {
                "uuid": str(uuid_value)
            }
        })
        
        # Check if a mapping was found
        if not result:
            raise ValueError(f"UUID {uuid_value} not found in registry")
            
        # Return the label
        return result[0]["label"]
    
    def get_uuid_for_label(self, label: str) -> uuid.UUID:
        """
        Get the UUID for a semantic label.
        
        If the label is not already registered, a new UUID will be
        generated and registered for it.
        
        Args:
            label: Semantic label to look up
            
        Returns:
            Corresponding UUID
        """
        # Construct the AQL query
        query = f"""
        FOR doc IN {self.registry_collection}
        FILTER doc.label == @label
        LIMIT 1
        RETURN doc
        """
        
        # Execute the query
        result = self.arango_query({
            "query": query,
            "bindVars": {
                "label": label
            }
        })
        
        # Check if a mapping was found
        if result:
            # Return the existing UUID
            return uuid.UUID(result[0]["_key"])
            
        # Generate a new UUID and store the mapping
        new_uuid = uuid.uuid4()
        self.store_mapping(label, new_uuid)
        
        return new_uuid