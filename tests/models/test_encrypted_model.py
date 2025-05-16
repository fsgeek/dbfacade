"""
Tests for encrypted fields in ObfuscatedModel.
"""

import os
import uuid
from typing import Dict, Any, Optional
from unittest.mock import patch

import pytest
from pydantic import Field

from indaleko_dbfacade.config import DBFacadeConfig
from indaleko_dbfacade.models import ObfuscatedField, ObfuscatedModel
from indaleko_dbfacade.models.obfuscated_model import ObfuscationLevel


class TestEncryptedModel:
    """Tests for encrypted fields in ObfuscatedModel."""
    
    def setup_method(self) -> None:
        """Set up the test environment."""
        # Save original environment variables
        self.original_env = {}
        for key in ["INDALEKO_MODE", "INDALEKO_ENCRYPTION_ENABLED", "INDALEKO_ENCRYPTION_KEY"]:
            self.original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]
                
        # Set up environment for testing
        os.environ["INDALEKO_MODE"] = "DEV"
        os.environ["INDALEKO_ENCRYPTION_ENABLED"] = "true"
        os.environ["INDALEKO_ENCRYPTION_KEY"] = "test-encryption-key-for-unit-tests"
        
        # Initialize configuration
        DBFacadeConfig.initialize()
    
    def teardown_method(self) -> None:
        """Clean up after the test."""
        # Restore original environment variables
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
    
    def test_model_with_encrypted_fields(self) -> None:
        """Test a model with encrypted fields."""
        
        # Define a model with encrypted fields
        class SensitiveData(ObfuscatedModel):
            username: str
            password: str = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
            api_key: str = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
            public_flag: bool = ObfuscatedField(obfuscation_level=ObfuscationLevel.NONE)
        
        # Create test UUIDs for the fields
        username_uuid = uuid.uuid4()
        password_uuid = uuid.uuid4()
        api_key_uuid = uuid.uuid4()
        public_flag_uuid = uuid.uuid4()
        model_uuid = uuid.uuid4()
        
        # Mock the registry client
        with patch("indaleko_dbfacade.registry.client.RegistryClient.get_uuid_for_label") as mock_get_uuid:
            # Configure the mock to return predictable UUIDs
            mock_get_uuid.side_effect = lambda label: {
                "username": username_uuid,
                "password": password_uuid,
                "api_key": api_key_uuid,
                "public_flag": public_flag_uuid,
                "SensitiveData": model_uuid,
            }.get(label, uuid.uuid4())
            
            # Create a model instance
            data = SensitiveData.create_from_semantic(
                username="testuser",
                password="secret123",
                api_key="api-key-12345",
                public_flag=True
            )
            
            # Check that the encrypted fields were encrypted
            raw_data = data.model_dump()
            assert "username" in raw_data  # Not encrypted, should be visible
            assert "password" in raw_data  # Encrypted, but visible in dev mode
            assert "api_key" in raw_data   # Encrypted, but visible in dev mode
            assert "public_flag" in raw_data  # Not encrypted, should be visible
            
            # Values should be decrypted in dev mode
            assert raw_data["username"] == "testuser"
            assert raw_data["password"] == "secret123"
            assert raw_data["api_key"] == "api-key-12345"
            assert raw_data["public_flag"] is True
    
    def test_encrypted_fields_in_prod_mode(self) -> None:
        """Test encrypted fields in production mode."""
        
        # Set production mode
        os.environ["INDALEKO_MODE"] = "PROD"
        DBFacadeConfig.initialize()
        
        # Define a model with encrypted fields
        class SensitiveData(ObfuscatedModel):
            username: str
            password: str = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
            api_key: str = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
        
        # Create test UUIDs for the fields
        username_uuid = uuid.uuid4()
        password_uuid = uuid.uuid4()
        api_key_uuid = uuid.uuid4()
        model_uuid = uuid.uuid4()
        
        # Mock the registry client
        with patch("indaleko_dbfacade.registry.client.RegistryClient.get_uuid_for_label") as mock_get_uuid:
            # Configure the mock to return predictable UUIDs
            mock_get_uuid.side_effect = lambda label: {
                "username": username_uuid,
                "password": password_uuid,
                "api_key": api_key_uuid,
                "SensitiveData": model_uuid,
            }.get(label, uuid.uuid4())
            
            # Create a model instance
            data = SensitiveData.create_from_semantic(
                username="testuser",
                password="secret123",
                api_key="api-key-12345"
            )
            
            # Get the raw data representation
            raw_data = data.model_dump()
            
            # In production mode, field names should be UUIDs
            str_username_uuid = str(username_uuid)
            str_password_uuid = str(password_uuid)
            str_api_key_uuid = str(api_key_uuid)
            
            # Check that UUID keys are used
            assert str_username_uuid in raw_data
            assert str_password_uuid in raw_data
            assert str_api_key_uuid in raw_data
            
            # Check that sensitive fields are encrypted
            # Password and API key should be encrypted dictionaries
            assert isinstance(raw_data[str_password_uuid], dict)
            assert "value" in raw_data[str_password_uuid]
            assert "metadata" in raw_data[str_password_uuid]
            
            assert isinstance(raw_data[str_api_key_uuid], dict)
            assert "value" in raw_data[str_api_key_uuid]
            assert "metadata" in raw_data[str_api_key_uuid]
            
            # Username should not be encrypted
            assert not isinstance(raw_data[str_username_uuid], dict)
            assert raw_data[str_username_uuid] == "testuser"
    
    def test_encryption_disabled(self) -> None:
        """Test behavior when encryption is disabled."""
        
        # Disable encryption
        os.environ["INDALEKO_ENCRYPTION_ENABLED"] = "false"
        DBFacadeConfig.initialize()
        
        # Define a model with encrypted fields
        class SensitiveData(ObfuscatedModel):
            username: str
            password: str = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
            api_key: str = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
        
        # Create a model instance
        data = SensitiveData.create_from_semantic(
            username="testuser",
            password="secret123",
            api_key="api-key-12345"
        )
        
        # Get the raw data representation
        raw_data = data.model_dump()
        
        # Fields should not be encrypted when encryption is disabled
        assert raw_data["username"] == "testuser"
        assert raw_data["password"] == "secret123"
        assert raw_data["api_key"] == "api-key-12345"