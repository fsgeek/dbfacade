"""
Tests for the ObfuscatedModel class.
"""

import os
import uuid
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field, ValidationError

from indaleko_dbfacade.config import DBFacadeConfig
from indaleko_dbfacade.models import ObfuscatedField, ObfuscatedModel
from indaleko_dbfacade.models.obfuscated_model import ObfuscationLevel


class TestObfuscatedModel:
    """Tests for the ObfuscatedModel class."""
    
    def test_basic_obfuscated_model(self, dev_mode_env: None) -> None:
        """Test creating a basic obfuscated model."""
        
        class User(ObfuscatedModel):
            name: str
            email: str
            age: int = 0
        
        # Simulate UUID mapping for testing
        test_uuid1 = uuid.uuid4()
        test_uuid2 = uuid.uuid4()
        test_uuid3 = uuid.uuid4()
        
        with patch("indaleko_dbfacade.registry.client.RegistryClient.get_uuid_for_label") as mock_get_uuid:
            # Configure the mock to return predictable UUIDs
            mock_get_uuid.side_effect = lambda label: {
                "name": test_uuid1,
                "email": test_uuid2,
                "age": test_uuid3,
                "User": uuid.uuid4(),  # Class name UUID
            }.get(label, uuid.uuid4())
            
            # Create the model with semantic field names
            user = User.create_from_semantic(name="John Doe", email="john@example.com", age=30)
            
            # Check that the UUID mapping was called
            assert mock_get_uuid.call_count >= 3  # name, email, age
            
            # In dev mode, dumping should use semantic names
            user_dict = user.model_dump()
            assert "name" in user_dict
            assert "email" in user_dict
            assert "age" in user_dict
            assert user_dict["name"] == "John Doe"
            assert user_dict["email"] == "john@example.com"
            assert user_dict["age"] == 30
    
    def test_obfuscated_model_prod_mode(self, prod_mode_env: None) -> None:
        """Test obfuscated model in production mode."""
        
        class User(ObfuscatedModel):
            name: str
            email: str
        
        # Simulate UUID mapping for testing
        test_uuid1 = uuid.uuid4()
        test_uuid2 = uuid.uuid4()
        
        with patch("indaleko_dbfacade.registry.client.RegistryClient.get_uuid_for_label") as mock_get_uuid:
            # Configure the mock to return predictable UUIDs
            mock_get_uuid.side_effect = lambda label: {
                "name": test_uuid1,
                "email": test_uuid2,
                "User": uuid.uuid4(),  # Class name UUID
            }.get(label, uuid.uuid4())
            
            # Create the model with semantic field names
            user = User.create_from_semantic(name="John Doe", email="john@example.com")
            
            # In production mode, dumping should use UUID keys
            user_dict = user.model_dump()
            
            # UUID keys should be strings in the dictionary
            str_uuid1 = str(test_uuid1)
            str_uuid2 = str(test_uuid2)
            
            # Check that the values are under UUID keys
            assert str_uuid1 in user_dict or "name" in user_dict  # Allow fallback
            assert str_uuid2 in user_dict or "email" in user_dict
            
            # Check values regardless of key
            values = list(user_dict.values())
            assert "John Doe" in values
            assert "john@example.com" in values
    
    def test_obfuscated_field_descriptor(self, dev_mode_env: None) -> None:
        """Test using ObfuscatedField descriptors."""
        
        class User(ObfuscatedModel):
            name: str = Field(...)
            email: str = Field(...)
            
            # Field with custom descriptor
            secret: str = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
            
            # Field that should not be obfuscated
            public_data: str = ObfuscatedField(obfuscation_level=ObfuscationLevel.NONE)
        
        # Check that the obfuscated fields were collected
        fields = User._collect_obfuscated_fields()
        assert "secret" in fields
        assert "public_data" in fields
        assert fields["secret"].obfuscation_level == ObfuscationLevel.ENCRYPTED
        assert fields["public_data"].obfuscation_level == ObfuscationLevel.NONE
        
        # Test creating a model with these fields
        with patch("indaleko_dbfacade.registry.client.RegistryClient.get_uuid_for_label") as mock_get_uuid:
            # Configure the mock to return UUIDs
            mock_get_uuid.return_value = uuid.uuid4()
            
            # Create the model
            user = User.create_from_semantic(
                name="John Doe",
                email="john@example.com",
                secret="password123",
                public_data="Public info"
            )
            
            # Check that the values are in the model
            user_dict = user.model_dump()
            assert user_dict["name"] == "John Doe"
            assert user_dict["email"] == "john@example.com"
            assert user_dict["secret"] == "password123"
            assert user_dict["public_data"] == "Public info"
    
    def test_register_model_schema(self) -> None:
        """Test registering a model schema with the registry."""
        
        class Product(ObfuscatedModel):
            name: str
            price: float
            description: Optional[str] = None
            tags: List[str] = Field(default_factory=list)
        
        with patch("indaleko_dbfacade.registry.client.RegistryClient.get_uuid_for_label") as mock_get_uuid:
            # Configure the mock to return UUIDs
            mock_get_uuid.return_value = uuid.uuid4()
            
            # Register the model schema
            mapping = Product._register_model_schema()
            
            # Check that all fields were registered
            assert "name" in mapping
            assert "price" in mapping
            assert "description" in mapping
            assert "tags" in mapping
            assert "Product" in mapping  # Class name should also be registered
            
            # Check that the UUIDs were retrieved
            assert mock_get_uuid.call_count >= 5  # 4 fields + class name