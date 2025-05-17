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


# Mock the ArangoDB client for tests
@pytest.fixture
def mock_db_client(monkeypatch):
    """Mock the ArangoDB client."""
    mock_client = mock.MagicMock(spec=ArangoDBClient)
    
    # Mock the insert method
    mock_client.insert.return_value = uuid.uuid4()
    
    # Mock the get method
    mock_client.get.return_value = {
        str(uuid.uuid4()): "test_username",
        str(uuid.uuid4()): "test@example.com",
        str(uuid.uuid4()): 25,
        str(uuid.uuid4()): True,
        str(uuid.uuid4()): datetime.now().isoformat()
    }
    
    # Mock the query method
    mock_client.query.return_value = [
        {
            str(uuid.uuid4()): "test_username",
            str(uuid.uuid4()): "test@example.com",
            str(uuid.uuid4()): 25
        },
        {
            str(uuid.uuid4()): "another_user",
            str(uuid.uuid4()): "another@example.com",
            str(uuid.uuid4()): 30
        }
    ]
    
    # Mock the update method
    mock_client.update.return_value = None
    
    # Mock the delete method
    mock_client.delete.return_value = None
    
    # Patch the ArangoDBClient constructor
    def mock_arango_client(*args, **kwargs):
        return mock_client
    
    monkeypatch.setattr("indaleko_dbfacade.db.arangodb.ArangoDBClient", mock_arango_client)
    
    return mock_client


# Mock the Registry client for tests
@pytest.fixture
def mock_registry_client(monkeypatch):
    """Mock the Registry client."""
    mock_client = mock.MagicMock(spec=RegistryClient)
    
    # UUID mapping for test fields
    field_uuids = {
        "TestUserModel": uuid.uuid4(),
        "username": uuid.uuid4(),
        "email": uuid.uuid4(),
        "age": uuid.uuid4(),
        "is_active": uuid.uuid4(),
        "created_at": uuid.uuid4(),
        "TestPostModel": uuid.uuid4(),
        "title": uuid.uuid4(),
        "content": uuid.uuid4(),
        "author_id": uuid.uuid4(),
        "views": uuid.uuid4(),
    }
    
    # Mock the get_uuid_for_label method
    def mock_get_uuid_for_label(label):
        if label in field_uuids:
            return field_uuids[label]
        # Generate and store a new UUID for unknown labels
        field_uuids[label] = uuid.uuid4()
        return field_uuids[label]
    
    mock_client.get_uuid_for_label.side_effect = mock_get_uuid_for_label
    
    # Mock the get_label_for_uuid method
    def mock_get_label_for_uuid(uuid_value):
        for label, uuid_val in field_uuids.items():
            if uuid_val == uuid_value:
                return label
        # Raise KeyError when a UUID is not found
        raise KeyError(f"UUID {uuid_value} not found in registry")
    
    mock_client.get_label_for_uuid.side_effect = mock_get_label_for_uuid
    
    # Mock the register_model_schema method
    def mock_register_model_schema(model_class):
        result = {}
        for field_name in model_class.__annotations__:
            if not field_name.startswith("_"):
                result[field_name] = mock_get_uuid_for_label(field_name)
        result[model_class.__name__] = mock_get_uuid_for_label(model_class.__name__)
        return result
    
    mock_client.register_model_schema.side_effect = mock_register_model_schema
    
    # Patch the Registry client constructor
    def mock_registry(*args, **kwargs):
        return mock_client
    
    monkeypatch.setattr("indaleko_dbfacade.registry.client.RegistryClient", mock_registry)
    
    return mock_client


# Tests
def test_db_facade_service_init(db_facade_service):
    """Test initializing the DB Facade Service."""
    assert db_facade_service is not None
    assert isinstance(db_facade_service, DBFacadeService)
    assert db_facade_service.db is not None
    assert db_facade_service.registry is not None


def test_store_model(db_facade_service, mock_db_client, mock_registry_client):
    """Test storing a model in the database."""
    # Create a test model
    user = TestUserModel(
        username="testuser",
        email="test@example.com",
        age=25
    )
    
    # Store the model
    record_uuid = db_facade_service.store_model(user)
    
    # Check that the registry was used to get the collection UUID
    mock_registry_client.get_uuid_for_label.assert_any_call("TestUserModel")
    
    # Check that the database client was used to insert the data
    mock_db_client.insert.assert_called_once()
    
    # Check that the record UUID was returned
    assert record_uuid is not None
    assert isinstance(record_uuid, uuid.UUID)


def test_get_model(db_facade_service, mock_db_client, mock_registry_client):
    """Test getting a model from the database."""
    # Create a test UUID
    record_uuid = uuid.uuid4()
    
    # Get the model
    user = db_facade_service.get_model(TestUserModel, record_uuid)
    
    # Check that the registry was used to get the collection UUID
    mock_registry_client.get_uuid_for_label.assert_any_call("TestUserModel")
    
    # Check that the database client was used to get the data
    mock_db_client.get.assert_called_once()
    
    # Check that the model was returned
    assert user is not None
    assert isinstance(user, TestUserModel)


def test_query_models(db_facade_service, mock_db_client, mock_registry_client):
    """Test querying models from the database."""
    # Create a test filter
    filter_dict = {"username": "testuser"}
    
    # Query the models
    users = db_facade_service.query_models(TestUserModel, filter_dict)
    
    # Check that the registry was used to get the collection UUID
    mock_registry_client.get_uuid_for_label.assert_any_call("TestUserModel")
    
    # Check that the registry was used to get the field UUID
    mock_registry_client.get_uuid_for_label.assert_any_call("username")
    
    # Check that the database client was used to query the data
    mock_db_client.query.assert_called_once()
    
    # Check that the models were returned
    assert users is not None
    assert isinstance(users, list)
    assert len(users) > 0
    assert all(isinstance(user, TestUserModel) for user in users)


def test_update_model(db_facade_service, mock_db_client, mock_registry_client):
    """Test updating a model in the database."""
    # Create a test model
    user = TestUserModel(
        username="testuser",
        email="test@example.com",
        age=25
    )
    
    # Create a test UUID
    record_uuid = uuid.uuid4()
    
    # Update the model
    db_facade_service.update_model(user, record_uuid)
    
    # Check that the registry was used to get the collection UUID
    mock_registry_client.get_uuid_for_label.assert_any_call("TestUserModel")
    
    # Check that the database client was used to update the data
    mock_db_client.update.assert_called_once()


def test_delete_model(db_facade_service, mock_db_client, mock_registry_client):
    """Test deleting a model from the database."""
    # Create a test UUID
    record_uuid = uuid.uuid4()
    
    # Delete the model
    db_facade_service.delete_model(TestUserModel, record_uuid)
    
    # Check that the registry was used to get the collection UUID
    mock_registry_client.get_uuid_for_label.assert_any_call("TestUserModel")
    
    # Check that the database client was used to delete the data
    mock_db_client.delete.assert_called_once()


def test_resolve_uuid_fields(db_facade_service, mock_registry_client):
    """Test resolving UUID fields to semantic names."""
    # Create test data with UUID keys
    test_uuid1 = uuid.uuid4()
    test_uuid2 = uuid.uuid4()
    data = {
        str(test_uuid1): "value1",
        str(test_uuid2): "value2"
    }
    
    # Mock the registry to return known labels for our UUIDs
    field_labels = {test_uuid1: "field1", test_uuid2: "field2"}
    
    def mock_get_label(uuid_value):
        if uuid_value in field_labels:
            return field_labels[uuid_value]
        raise KeyError(f"UUID {uuid_value} not found")
    
    mock_registry_client.get_label_for_uuid.side_effect = mock_get_label
    
    # Resolve the UUIDs
    resolved = db_facade_service.resolve_uuid_fields(data)
    
    # Check that the registry was used to resolve the UUIDs
    assert mock_registry_client.get_label_for_uuid.call_count == 2
    
    # Check that the fields were resolved
    assert resolved is not None
    assert isinstance(resolved, dict)
    assert len(resolved) == 2
    assert str(test_uuid1) in resolved
    assert str(test_uuid2) in resolved
    assert resolved[str(test_uuid1)] == "field1"
    assert resolved[str(test_uuid2)] == "field2"


def test_register_model_schema(db_facade_service, mock_registry_client):
    """Test registering a model schema with the registry."""
    # Register the model schema
    mapping = db_facade_service.register_model_schema(TestUserModel)
    
    # Check that the registry was used to register the model
    mock_registry_client.register_model_schema.assert_called_once_with(TestUserModel)
    
    # Check that the mapping was returned
    assert mapping is not None
    assert isinstance(mapping, dict)


def test_fail_stop_behavior_db_init():
    """Test fail-stop behavior for database initialization."""
    # In the test environment, MCP functions aren't available,
    # so the ArangoDBClient should fail with SystemExit
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
    
    # Check that the service raises a ValueError
    with pytest.raises(ValueError):
        db_facade_service.store_model(invalid_model)
    
    # Try to get a model with an invalid class
    with pytest.raises(TypeError):
        db_facade_service.get_model(InvalidModel, uuid.uuid4())
    
    # Try to query models with an invalid class
    with pytest.raises(TypeError):
        db_facade_service.query_models(InvalidModel, {})
    
    # Try to update a model with an invalid class
    with pytest.raises(ValueError):
        db_facade_service.update_model(invalid_model, uuid.uuid4())
    
    # Try to delete a model with an invalid class
    with pytest.raises(TypeError):
        db_facade_service.delete_model(InvalidModel, uuid.uuid4())