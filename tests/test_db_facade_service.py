"""
Tests for the DB Facade Service.

These tests verify that the DB Facade Service correctly interacts with
ArangoDB and provides the expected behavior for database operations.
"""

import os
import sys
import uuid
from datetime import datetime
from typing import cast

import pytest
from pydantic import BaseModel, Field

from indaleko_dbfacade.db_facade_service import DBFacadeService
from indaleko_dbfacade.models.obfuscated_model import ObfuscatedModel
from indaleko_dbfacade.registry.client import RegistryClient
from indaleko_dbfacade.db.arangodb import ArangoDBClient
from indaleko_dbfacade.config import DBFacadeConfig


# Test models (prefix underscore to avoid pytest collection warning)
class _TestUserModel(ObfuscatedModel):
    """Test user model for DB Facade Service tests."""
    
    username: str
    email: str
    age: int
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)


class _TestPostModel(ObfuscatedModel):
    """Test post model for DB Facade Service tests."""
    
    title: str
    content: str
    author_id: uuid.UUID
    views: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


# Fixtures
@pytest.fixture
def db_facade_service():
    """Fixture for the DB Facade Service."""
    # Set test environment
    os.environ["INDALEKO_MODE"] = "DEV"
    
    # Initialize configuration with secrets file
    secrets_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".secrets", "db_config.yaml"
    )
    
    DBFacadeConfig.initialize()
    if os.path.exists(secrets_file):
        DBFacadeConfig.load_from_secrets_file(secrets_file)
    else:
        print(f"Secrets file not found: {secrets_file}", file=sys.stderr)
        sys.exit(1)
    
    service = DBFacadeService(
        registry_collection="test_registry",
        data_collection="test_data"
    )
    
    return service


# No mock fixtures - we'll use real database and registry connections


# Tests
def test_db_facade_service_init(db_facade_service):
    """Test initializing the DB Facade Service."""
    assert db_facade_service is not None
    assert isinstance(db_facade_service, DBFacadeService)
    assert db_facade_service.db is not None
    assert db_facade_service.registry is not None


def test_store_model(db_facade_service):
    """Test storing a model in the database."""
    # Create a test model
    user = _TestUserModel(
        username="testuser",
        email="test@example.com",
        age=25
    )
    
    # Store the model
    record_uuid = db_facade_service.store_model(user)
    
    # Check that the record UUID was returned
    assert record_uuid is not None
    assert isinstance(record_uuid, uuid.UUID)


def test_get_model(db_facade_service):
    """Test getting a model from the database."""
    # First store a model
    user = _TestUserModel(
        username="getuser",
        email="get@example.com",
        age=30
    )
    
    # Store the model and get its UUID
    record_uuid = db_facade_service.store_model(user)
    
    # Get the model back
    retrieved_user = db_facade_service.get_model(_TestUserModel, record_uuid)
    
    # Check that the model was returned with correct data
    assert retrieved_user is not None
    assert isinstance(retrieved_user, _TestUserModel)
    # In dev mode, we should get semantic names back
    assert retrieved_user.username == "getuser"
    assert retrieved_user.email == "get@example.com"
    assert retrieved_user.age == 30


def test_query_models(db_facade_service):
    """Test querying models from the database."""
    # Store multiple test models
    users = [
        _TestUserModel(username="query1", email="query1@example.com", age=25),
        _TestUserModel(username="query2", email="query2@example.com", age=30),
        _TestUserModel(username="query1", email="duplicate@example.com", age=35),
    ]
    
    for user in users:
        db_facade_service.store_model(user)
    
    # Query for users with username "query1"
    filter_dict = {"username": "query1"}
    results = db_facade_service.query_models(_TestUserModel, filter_dict)
    
    # Check that we found the correct users
    assert len(results) >= 2  # At least 2 users with username "query1"
    for user in results:
        assert isinstance(user, _TestUserModel)
        assert user.username == "query1"


def test_update_model(db_facade_service):
    """Test updating a model in the database."""
    # Create and store a model
    user = _TestUserModel(
        username="updateuser",
        email="update@example.com",
        age=40
    )
    
    record_uuid = db_facade_service.store_model(user)
    
    # Update the model
    user.age = 41
    user.email = "updated@example.com"
    
    db_facade_service.update_model(user, record_uuid)
    
    # Get the model back and check updates
    updated_user = db_facade_service.get_model(_TestUserModel, record_uuid)
    assert updated_user.age == 41
    assert updated_user.email == "updated@example.com"
    assert updated_user.username == "updateuser"  # Should remain unchanged


def test_delete_model(db_facade_service):
    """Test deleting a model from the database."""
    # Create and store a model
    user = _TestUserModel(
        username="deleteuser",
        email="delete@example.com",
        age=50
    )
    
    record_uuid = db_facade_service.store_model(user)
    
    # Delete the model
    db_facade_service.delete_model(_TestUserModel, record_uuid)
    
    # Try to get the model - should raise ValueError
    with pytest.raises(ValueError):
        db_facade_service.get_model(_TestUserModel, record_uuid)


def test_resolve_uuid_fields(db_facade_service):
    """Test resolving UUID fields to their semantic names."""
    # Create UUID data (like what would come from the database)
    uuid_data = {}
    for i in range(3):
        field_uuid = str(uuid.uuid4())
        uuid_data[field_uuid] = f"value_{i}"
    
    # Resolve the UUIDs to semantic names
    resolved_data = db_facade_service.resolve_uuid_fields(uuid_data)
    
    # In dev mode, this should attempt to resolve UUIDs
    # Since these are random UUIDs, they may not resolve, but the method should not fail
    assert resolved_data is not None
    assert isinstance(resolved_data, dict)


def test_register_model_schema(db_facade_service):
    """Test registering a model schema with the registry."""
    # Register the model schema
    mapping = db_facade_service.register_model_schema(_TestUserModel)
    
    # Check that we got a mapping back
    assert mapping is not None
    assert isinstance(mapping, dict)
    
    # The mapping should include field names and the class name
    assert "_TestUserModel" in mapping
    assert "username" in mapping
    assert "email" in mapping
    assert "age" in mapping


def test_fail_stop_behavior_db_init():
    """Test fail-stop behavior for database initialization."""
    # In the test environment, if we don't set up the proper config,
    # the ArangoDBClient should fail with SystemExit
    with pytest.raises(SystemExit) as excinfo:
        from indaleko_dbfacade.db.arangodb import ArangoDBClient
        ArangoDBClient()
    
    # Check that the exit code is 1
    assert excinfo.value.code == 1


def test_fail_stop_behavior_registry_init():
    """Test fail-stop behavior for registry initialization."""
    # The RegistryClient should fail if the registry is unavailable
    # Set an invalid registry URL to test failure behavior
    os.environ["INDALEKO_REGISTRY_URL"] = "http://invalid-registry:0000"
    DBFacadeConfig.initialize()
    
    with pytest.raises(SystemExit) as excinfo:
        from indaleko_dbfacade.registry.client import RegistryClient
        RegistryClient()
    
    # Check that the exit code is 1
    assert excinfo.value.code == 1


def test_fail_stop_behavior_invalid_model(db_facade_service):
    """Test fail-stop behavior for invalid models."""
    # Try to store a non-ObfuscatedModel
    class InvalidModel(BaseModel):
        name: str
    
    invalid_model = InvalidModel(name="test")
    
    # This should raise a ValueError
    with pytest.raises(ValueError):
        db_facade_service.store_model(invalid_model)