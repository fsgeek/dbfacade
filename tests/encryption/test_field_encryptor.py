"""
Tests for the FieldEncryptor class.
"""

import json
import os
import uuid
from typing import Dict, Any, Optional, cast
from unittest.mock import patch

import pytest

from indaleko_dbfacade.encryption import FieldEncryptor, EncryptionAlgorithm, EncryptionMetadata
from indaleko_dbfacade.config import DBFacadeConfig


class TestFieldEncryptor:
    """Tests for the FieldEncryptor class."""
    
    def setup_method(self) -> None:
        """Set up the test environment."""
        # Reset environment variables
        if "INDALEKO_ENCRYPTION_KEY" in os.environ:
            del os.environ["INDALEKO_ENCRYPTION_KEY"]
            
        # Set a test master key
        os.environ["INDALEKO_ENCRYPTION_KEY"] = "test-master-key-for-unit-testing"
        
        # Ensure DEV mode
        os.environ["INDALEKO_MODE"] = "DEV"
        DBFacadeConfig.initialize()
    
    def teardown_method(self) -> None:
        """Clean up after tests."""
        # Clean up environment variables
        if "INDALEKO_ENCRYPTION_KEY" in os.environ:
            del os.environ["INDALEKO_ENCRYPTION_KEY"]
    
    def test_field_encryption_decryption(self) -> None:
        """Test encrypting and decrypting a field value."""
        # Create a field encryptor
        encryptor = FieldEncryptor()
        
        # Create a test field UUID
        field_uuid = uuid.uuid4()
        
        # Test with different types of values
        test_values = [
            "simple string",
            123,
            3.14,
            True,
            ["list", "of", "values"],
            {"key": "value", "nested": {"a": 1, "b": 2}},
            None,
        ]
        
        for value in test_values:
            # Encrypt the value
            encrypted_data = encryptor.encrypt_field(value, field_uuid)
            
            # Check the structure of the encrypted data
            assert "value" in encrypted_data
            assert "metadata" in encrypted_data
            assert "algorithm" in encrypted_data["metadata"]
            assert "iv" in encrypted_data["metadata"]
            assert "salt" in encrypted_data["metadata"]
            assert "created_at" in encrypted_data["metadata"]
            
            # Decrypt the value
            decrypted_value = encryptor.decrypt_field(encrypted_data, field_uuid)
            
            # Check that the decrypted value matches the original
            assert decrypted_value == value
    
    def test_key_derivation(self) -> None:
        """Test key derivation from master key and field UUID."""
        # Create a field encryptor
        encryptor = FieldEncryptor(master_key="test-encryption-key")
        
        # Create test field UUIDs
        field_uuid1 = uuid.uuid4()
        field_uuid2 = uuid.uuid4()
        
        # Derive keys for the same field with the same salt
        salt = os.urandom(16)
        key1a, _ = encryptor.derive_key(field_uuid1, salt)
        key1b, _ = encryptor.derive_key(field_uuid1, salt)
        
        # Derive a key for a different field with the same salt
        key2, _ = encryptor.derive_key(field_uuid2, salt)
        
        # Check that keys for the same field and salt are the same
        assert key1a == key1b
        
        # Check that keys for different fields are different
        assert key1a != key2
    
    def test_string_convenience_methods(self) -> None:
        """Test convenience methods for string-based encryption/decryption."""
        # Create a field encryptor
        encryptor = FieldEncryptor()
        
        # Create a test field UUID
        field_uuid = uuid.uuid4()
        
        # Test value
        test_value = {"name": "John Doe", "email": "john@example.com", "age": 30}
        
        # Encrypt to JSON string
        encrypted_json = encryptor.encrypt_value(test_value, field_uuid)
        
        # Check that the encrypted value is a valid JSON string
        assert isinstance(encrypted_json, str)
        encrypted_data = json.loads(encrypted_json)
        assert "value" in encrypted_data
        assert "metadata" in encrypted_data
        
        # Decrypt from JSON string
        decrypted_value = encryptor.decrypt_value(encrypted_json, field_uuid)
        
        # Check that the decrypted value matches the original
        assert decrypted_value == test_value
    
    def test_encryption_algorithm(self) -> None:
        """Test encryption with different algorithms."""
        # Create a field encryptor
        encryptor = FieldEncryptor()
        
        # Create a test field UUID
        field_uuid = uuid.uuid4()
        
        # Test value
        test_value = "secret message"
        
        # Encrypt with AES-GCM
        encrypted_data = encryptor.encrypt_field(
            test_value, field_uuid, algorithm=EncryptionAlgorithm.AES_GCM
        )
        
        # Check the algorithm in metadata
        assert encrypted_data["metadata"]["algorithm"] == EncryptionAlgorithm.AES_GCM.value
        
        # Decrypt and verify
        decrypted_value = encryptor.decrypt_field(encrypted_data, field_uuid)
        assert decrypted_value == test_value
    
    def test_master_key_from_environment(self) -> None:
        """Test getting the master key from environment variables."""
        # Set environment variable
        os.environ["INDALEKO_ENCRYPTION_KEY"] = "env-master-key"
        
        # Create a field encryptor
        encryptor = FieldEncryptor()
        
        # Check that it used the environment variable
        assert encryptor.master_key == "env-master-key"
    
    def test_metadata_serialization(self) -> None:
        """Test serialization of encryption metadata."""
        # Create metadata
        metadata = EncryptionMetadata(
            algorithm=EncryptionAlgorithm.AES_GCM,
            iv="base64-iv-data",
            salt="base64-salt-data",
            created_at="2023-01-01T00:00:00Z",
            version="1.0",
        )
        
        # Convert to dictionary
        metadata_dict = metadata.to_dict()
        
        # Check dictionary structure
        assert metadata_dict["algorithm"] == EncryptionAlgorithm.AES_GCM.value
        assert metadata_dict["iv"] == "base64-iv-data"
        assert metadata_dict["salt"] == "base64-salt-data"
        assert metadata_dict["created_at"] == "2023-01-01T00:00:00Z"
        assert metadata_dict["version"] == "1.0"
        
        # Recreate from dictionary
        new_metadata = EncryptionMetadata.from_dict(metadata_dict)
        
        # Check that the recreated metadata matches the original
        assert new_metadata.algorithm == metadata.algorithm
        assert new_metadata.iv == metadata.iv
        assert new_metadata.salt == metadata.salt
        assert new_metadata.created_at == metadata.created_at
        assert new_metadata.version == metadata.version
    
    def test_dev_mode_default_key(self) -> None:
        """Test using the default key in development mode."""
        # Remove any environment variables
        if "INDALEKO_ENCRYPTION_KEY" in os.environ:
            del os.environ["INDALEKO_ENCRYPTION_KEY"]
        
        # Ensure DEV mode
        os.environ["INDALEKO_MODE"] = "DEV"
        DBFacadeConfig.initialize()
        
        # Create a field encryptor (should use dev-only key)
        encryptor = FieldEncryptor()
        
        # Verify it's using the dev-only key
        assert "dev-only" in encryptor.master_key
        
        # Test that encryption still works
        field_uuid = uuid.uuid4()
        test_value = "test string"
        encrypted_data = encryptor.encrypt_field(test_value, field_uuid)
        decrypted_value = encryptor.decrypt_field(encrypted_data, field_uuid)
        assert decrypted_value == test_value
    
    def test_prod_mode_requires_key(self) -> None:
        """Test that production mode requires a real key."""
        # Remove any environment variables
        if "INDALEKO_ENCRYPTION_KEY" in os.environ:
            del os.environ["INDALEKO_ENCRYPTION_KEY"]
        
        # Set PROD mode
        os.environ["INDALEKO_MODE"] = "PROD"
        DBFacadeConfig.initialize()
        
        # Creating an encryptor should fail in PROD mode without a key
        with pytest.raises(SystemExit):
            FieldEncryptor()