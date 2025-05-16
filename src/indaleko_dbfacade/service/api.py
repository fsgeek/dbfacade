"""
DB Facade Service API implementation.

This module provides the REST API for the DB Facade service, allowing
clients to interact with the database using obfuscated field names.
"""

import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Type, TypeVar, cast, Callable

from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, Field, ValidationError
import uvicorn

from ..config import DBFacadeConfig
from ..models import ObfuscatedModel


# API models for requests and responses
class RecordPayload(BaseModel):
    """Payload for submitting a record to the database."""
    
    collection: uuid.UUID  # UUID of the collection, not a name
    data: Dict[str, Any]  # All keys must be UUIDs (field names)


class RecordResponse(BaseModel):
    """Response for a record submission."""
    
    record_uuid: uuid.UUID
    collection: uuid.UUID
    stored_at: str


class QueryPayload(BaseModel):
    """Payload for querying records."""
    
    collection: uuid.UUID
    filter: Dict[str, Any]  # UUID-based filter
    limit: Optional[int] = 50
    dev_mode: Optional[bool] = False  # Override development mode


class QueryResult(BaseModel):
    """Result of a query operation."""
    
    results: List[Dict[str, Any]]
    resolved_fields: Optional[Dict[str, str]] = None  # Only in dev_mode


# Initialize the FastAPI app
app = FastAPI(
    title="DB Facade Service",
    description="A database obfuscation layer that protects semantic field names",
    version="0.1.0",
)


# Database connection dependency
def get_db():
    """Get a database connection."""
    # Use the ArangoDB client
    from ..db.arangodb import ArangoDBClient
    
    # Return a new ArangoDB client instance
    return ArangoDBClient()


# API endpoints
@app.post("/record", response_model=RecordResponse)
def submit_record(payload: RecordPayload, db=Depends(get_db)) -> RecordResponse:
    """
    Submit a record to the database.
    
    Args:
        payload: Record payload containing collection and data
        db: Database connection
        
    Returns:
        Record response with the record UUID
    """
    try:
        # Insert the record into the database
        record_uuid = db.insert(payload.collection, payload.data)
        
        # Return the response
        return RecordResponse(
            record_uuid=record_uuid,
            collection=payload.collection,
            stored_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        # Log the error and raise an HTTP exception
        print(f"[ERROR] Failed to submit record: {e}", file=sys.stderr)
        
        # In development mode, include the error details
        if DBFacadeConfig.is_dev_mode():
            raise HTTPException(status_code=500, detail=str(e))
        else:
            # In production, use a generic error message
            raise HTTPException(status_code=500, detail="Failed to submit record")


@app.post("/query", response_model=QueryResult)
def run_query(payload: QueryPayload, db=Depends(get_db)) -> QueryResult:
    """
    Run a query against the database.
    
    Args:
        payload: Query payload containing collection and filter
        db: Database connection
        
    Returns:
        Query result with the matching records
    """
    try:
        # Use dev_mode from payload if provided, otherwise use config
        dev_mode = payload.dev_mode if payload.dev_mode is not None else DBFacadeConfig.is_dev_mode()
        
        # Run the query against the database
        results = db.query(payload.collection, payload.filter, payload.limit)
        
        # In development mode, resolve UUIDs to semantic field names
        resolved_fields = None
        if dev_mode:
            # Use the registry to resolve UUIDs to semantic field names
            from ..db_facade_service import DBFacadeService
            
            # Create a DB Facade Service instance
            service = DBFacadeService()
            
            # Check if we have results to resolve
            if results and len(results) > 0:
                # Use the first result to get field mappings
                first_result = results[0]
                
                # Resolve UUIDs to semantic names
                resolved_fields = service.resolve_uuid_fields(first_result)
            
        # Return the query result
        return QueryResult(results=results, resolved_fields=resolved_fields)
    except Exception as e:
        # Log the error and raise an HTTP exception
        print(f"[ERROR] Failed to run query: {e}", file=sys.stderr)
        
        # In development mode, include the error details
        if DBFacadeConfig.is_dev_mode():
            raise HTTPException(status_code=500, detail=str(e))
        else:
            # In production, use a generic error message
            raise HTTPException(status_code=500, detail="Failed to run query")


@app.get("/record/{record_uuid}", response_model=Dict[str, Any])
def get_record(
    record_uuid: uuid.UUID, 
    collection: uuid.UUID = Query(..., description="UUID of the collection"),
    dev_mode: bool = Query(None, description="Override development mode"),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """
    Get a record from the database.
    
    Args:
        record_uuid: UUID of the record to retrieve
        collection: UUID of the collection containing the record
        dev_mode: Override development mode
        db: Database connection
        
    Returns:
        The record data
    """
    try:
        # Use dev_mode from query param if provided, otherwise use config
        dev_mode = dev_mode if dev_mode is not None else DBFacadeConfig.is_dev_mode()
        
        # Get the record from the database
        record = db.get(collection, record_uuid)
        
        # In development mode, resolve UUIDs to semantic field names
        if dev_mode:
            # Use the registry to resolve UUIDs to semantic field names
            from ..db_facade_service import DBFacadeService
            
            # Create a DB Facade Service instance
            service = DBFacadeService()
            
            # Resolve UUIDs to semantic names and create a new dictionary
            resolved_record = {}
            
            for field_uuid, value in record.items():
                try:
                    field_name = service.registry.get_label_for_uuid(uuid.UUID(field_uuid))
                    resolved_record[field_name] = value
                except (ValueError, KeyError):
                    # If we can't resolve the UUID, use it as is
                    resolved_record[field_uuid] = value
            
            # Use the resolved record
            record = resolved_record
            
        return record
    except Exception as e:
        # Log the error and raise an HTTP exception
        print(f"[ERROR] Failed to get record: {e}", file=sys.stderr)
        
        # In development mode, include the error details
        if DBFacadeConfig.is_dev_mode():
            raise HTTPException(status_code=500, detail=str(e))
        else:
            # In production, use a generic error message
            raise HTTPException(status_code=404, detail="Record not found")


@app.get("/health")
def health_check() -> Dict[str, str]:
    """
    Check the health of the service.
    
    Returns:
        Health status
    """
    return {"status": "ok", "mode": DBFacadeConfig.get("mode")}


def start_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """
    Start the API server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Whether to enable auto-reload
    """
    uvicorn.run(
        "indaleko_dbfacade.service.api:app",
        host=host,
        port=port,
        reload=reload,
    )