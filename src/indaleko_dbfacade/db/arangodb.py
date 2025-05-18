"""
ArangoDB client for DB Facade.

This module provides a client for connecting to ArangoDB using
the python-arango driver, designed for the DB Facade service.
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import cast

from arango import ArangoClient
from arango.cursor import Cursor
from arango.exceptions import (
    ArangoError,
    CollectionCreateError,
    DocumentInsertError,
    DocumentGetError,
    DocumentUpdateError,
    DocumentDeleteError,
)

from ..config import DBFacadeConfig


class ArangoDBClient:
    """
    ArangoDB client for DB Facade.
    
    This client interacts with ArangoDB using the python-arango driver,
    providing methods for CRUD operations on collections and documents.
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
        
        # Get database configuration
        db_config = DBFacadeConfig.get_database_credentials()
        db_url = DBFacadeConfig.get_database_url()
        
        try:
            # Initialize ArangoDB client
            self.client = ArangoClient(hosts=db_url)
            
            # Connect to the database
            self.db = self.client.db(
                name=db_config["database"],
                username=db_config["username"],
                password=db_config["password"],
                auth_method="basic",
                verify=True
            )
            
            # Verify connection
            self.db.properties()  # This will raise an exception if connection fails
            
        except ArangoError as e:
            print(f"Failed to connect to ArangoDB: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error connecting to database: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Verify collections exist
        self._ensure_collections_exist()
    
    def _ensure_collections_exist(self) -> None:
        """
        Ensure that the necessary collections exist in the database.
        
        If the collections don't exist, they will be created.
        """
        try:
            existing_collections = [col["name"] for col in self.db.collections()]
            
            # Create registry collection if it doesn't exist
            if self.registry_collection not in existing_collections:
                print(f"Creating collection: {self.registry_collection}")
                self.db.create_collection(self.registry_collection)
                
            # Create data collection if it doesn't exist
            if self.data_collection not in existing_collections:
                print(f"Creating collection: {self.data_collection}")
                self.db.create_collection(self.data_collection)
                
        except CollectionCreateError as e:
            print(f"Failed to create collection: {e}", file=sys.stderr)
            sys.exit(1)
        except ArangoError as e:
            print(f"Failed to list collections: {e}", file=sys.stderr)
            sys.exit(1)
    
    def insert(self, collection_uuid: uuid.UUID, data: dict[str, object]) -> uuid.UUID:
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
        
        try:
            # Insert the document
            collection = self.db.collection(self.data_collection)
            collection.insert(document)
            return doc_uuid
            
        except DocumentInsertError as e:
            print(f"Failed to insert document: {e}", file=sys.stderr)
            sys.exit(1)
        except ArangoError as e:
            print(f"Database error during insert: {e}", file=sys.stderr)
            sys.exit(1)
    
    def query(
        self, 
        collection_uuid: uuid.UUID, 
        filter_dict: dict[str, object],
        limit: int = 50
    ) -> list[dict[str, object]]:
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
        
        
        try:
            # Execute the query
            cursor = self.db.aql.execute(
                query,
                bind_vars=bind_vars,
                batch_size=1000
            )
            
            # Extract the data from each document
            results = []
            for doc in cursor:
                results.append(doc["data"])
            
            return results
            
        except ArangoError as e:
            print(f"Query failed: {e}", file=sys.stderr)
            sys.exit(1)
    
    def get(self, collection_uuid: uuid.UUID, record_uuid: uuid.UUID) -> dict[str, object]:
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
        
        try:
            # Execute the query
            cursor = self.db.aql.execute(
                query,
                bind_vars={
                    "record_uuid": str(record_uuid),
                    "collection_uuid": str(collection_uuid)
                }
            )
            
            # Get the result
            results = list(cursor)
            
            # Check if a document was found
            if not results:
                raise ValueError(f"Document with UUID {record_uuid} not found")
                
            # Return the document data
            return results[0]["data"]
            
        except ValueError:
            raise  # Re-raise ValueError as is
        except ArangoError as e:
            print(f"Failed to get document: {e}", file=sys.stderr)
            sys.exit(1)
    
    def update(
        self, 
        collection_uuid: uuid.UUID, 
        record_uuid: uuid.UUID, 
        data: dict[str, object]
    ) -> None:
        """
        Update a document in the database.
        
        Args:
            collection_uuid: UUID of the collection
            record_uuid: UUID of the document
            data: Updated document data with UUID keys
        """
        # Prepare the update
        update_doc = {
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Update the document
            collection = self.db.collection(self.data_collection)
            collection.update({
                "_key": str(record_uuid),
                **update_doc
            })
            
        except DocumentUpdateError as e:
            print(f"Failed to update document: {e}", file=sys.stderr)
            sys.exit(1)
        except ArangoError as e:
            print(f"Database error during update: {e}", file=sys.stderr)
            sys.exit(1)
    
    def delete(self, collection_uuid: uuid.UUID, record_uuid: uuid.UUID) -> None:
        """
        Delete a document from the database.
        
        Args:
            collection_uuid: UUID of the collection
            record_uuid: UUID of the document
        """
        try:
            # Delete the document
            collection = self.db.collection(self.data_collection)
            collection.delete(str(record_uuid))
            
        except DocumentDeleteError as e:
            print(f"Failed to delete document: {e}", file=sys.stderr)
            sys.exit(1)
        except ArangoError as e:
            print(f"Database error during delete: {e}", file=sys.stderr)
            sys.exit(1)
    
    def close(self) -> None:
        """
        Close the database connection.
        """
        try:
            self.client.close()
        except Exception as e:
            print(f"Error closing database connection: {e}", file=sys.stderr)