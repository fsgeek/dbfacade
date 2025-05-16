"""
Tests for the DB Facade Service API.
"""

import json
import os
import uuid
from typing import Dict, Any, Generator

import pytest
from fastapi.testclient import TestClient

from indaleko_dbfacade.config import DBFacadeConfig
from indaleko_dbfacade.service.api import app


@pytest.fixture
def client() -> TestClient:
    """
    Create a test client for the FastAPI app.
    
    Returns:
        TestClient: FastAPI test client
    """
    return TestClient(app)


class TestDBFacadeServiceAPI:
    """Tests for the DB Facade Service API."""
    
    def setup_method(self) -> None:
        """Set up the test environment."""
        # Save original environment variables
        self.original_env = {}
        for key in ["INDALEKO_MODE"]:
            self.original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]
                
        # Set development mode
        os.environ["INDALEKO_MODE"] = "DEV"
        DBFacadeConfig.initialize()
    
    def teardown_method(self) -> None:
        """Clean up after the test."""
        # Restore original environment variables
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
    
    def test_health_check(self, client: TestClient) -> None:
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["mode"] == "DEV"
    
    def test_submit_record(self, client: TestClient) -> None:
        """Test submitting a record."""
        # Create a test payload
        collection_uuid = uuid.uuid4()
        data = {
            str(uuid.uuid4()): "value1",
            str(uuid.uuid4()): "value2",
        }
        
        payload = {
            "collection": str(collection_uuid),
            "data": data,
        }
        
        # Submit the record
        response = client.post("/record", json=payload)
        
        # Check the response
        assert response.status_code == 200
        response_data = response.json()
        assert "record_uuid" in response_data
        assert response_data["collection"] == str(collection_uuid)
        assert "stored_at" in response_data
    
    def test_run_query(self, client: TestClient) -> None:
        """Test running a query."""
        # Create a test payload
        collection_uuid = uuid.uuid4()
        filter_data = {
            str(uuid.uuid4()): "value1",
        }
        
        payload = {
            "collection": str(collection_uuid),
            "filter": filter_data,
            "limit": 10,
            "dev_mode": True,
        }
        
        # Run the query
        response = client.post("/query", json=payload)
        
        # Check the response
        assert response.status_code == 200
        response_data = response.json()
        assert "results" in response_data
        assert isinstance(response_data["results"], list)
        assert "resolved_fields" in response_data
        assert isinstance(response_data["resolved_fields"], dict)
    
    def test_get_record(self, client: TestClient) -> None:
        """Test getting a record."""
        # Create a test record UUID and collection UUID
        record_uuid = uuid.uuid4()
        collection_uuid = uuid.uuid4()
        
        # Get the record
        response = client.get(
            f"/record/{record_uuid}?collection={collection_uuid}&dev_mode=true"
        )
        
        # Check the response
        assert response.status_code == 200
        response_data = response.json()
        assert "mock_field" in response_data
    
    def test_production_mode(self, client: TestClient) -> None:
        """Test API behavior in production mode."""
        # Set production mode
        os.environ["INDALEKO_MODE"] = "PROD"
        DBFacadeConfig.initialize()
        
        # Check health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["mode"] == "PROD"
        
        # Test error handling in production mode
        # This should return a generic error instead of details
        response = client.get("/record/invalid-uuid?collection=invalid-uuid")
        assert response.status_code == 404
        assert response.json()["detail"] == "Record not found"