"""
Tests for the DBFacadeConfig class.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from indaleko_dbfacade.config import DBFacadeConfig


class TestDBFacadeConfig:
    """Tests for the DBFacadeConfig class."""
    
    def setup_method(self) -> None:
        """Set up the test environment."""
        # Reset the configuration state before each test
        DBFacadeConfig._config = {}
        DBFacadeConfig._initialized = False
        
        # Save original environment variables
        self.original_env = {}
        for key in ["INDALEKO_MODE", "INDALEKO_ENCRYPTION_ENABLED", 
                   "INDALEKO_DB_URL", "INDALEKO_REGISTRY_URL"]:
            self.original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]
    
    def teardown_method(self) -> None:
        """Clean up after the test."""
        # Restore original environment variables
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]
    
    def test_default_config(self) -> None:
        """Test the default configuration values."""
        # Get a configuration value to trigger initialization
        mode = DBFacadeConfig.get("mode")
        assert mode == "DEV"  # Default mode
        
        # Check other default values
        assert DBFacadeConfig.get("encryption.enabled") is False
        assert DBFacadeConfig.get("registry.url") == "http://localhost:8000"
        assert DBFacadeConfig.get("database.url") == "http://localhost:8529"
    
    def test_environment_override(self) -> None:
        """Test overriding configuration with environment variables."""
        # Set environment variables
        os.environ["INDALEKO_MODE"] = "PROD"
        os.environ["INDALEKO_ENCRYPTION_ENABLED"] = "true"
        os.environ["INDALEKO_DB_URL"] = "http://db.example.com:8529"
        os.environ["INDALEKO_REGISTRY_URL"] = "http://registry.example.com:8000"
        
        # Re-initialize the configuration
        DBFacadeConfig.initialize()
        
        # Check that the environment values were used
        assert DBFacadeConfig.get("mode") == "PROD"
        assert DBFacadeConfig.get("encryption.enabled") is True
        assert DBFacadeConfig.get("database.url") == "http://db.example.com:8529"
        assert DBFacadeConfig.get("registry.url") == "http://registry.example.com:8000"
    
    def test_file_config(self) -> None:
        """Test loading configuration from a file."""
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "mode": "PROD",
                "encryption": {
                    "enabled": True,
                    "algorithm": "ChaCha20Poly1305"
                },
                "database": {
                    "url": "http://custom-db.example.com:8529"
                }
            }, f)
            config_path = f.name
        
        try:
            # Initialize with the config file
            DBFacadeConfig.initialize(config_path)
            
            # Check that the file values were used
            assert DBFacadeConfig.get("mode") == "PROD"
            assert DBFacadeConfig.get("encryption.enabled") is True
            assert DBFacadeConfig.get("encryption.algorithm") == "ChaCha20Poly1305"
            assert DBFacadeConfig.get("database.url") == "http://custom-db.example.com:8529"
            
            # A value not in the file should use the default
            assert DBFacadeConfig.get("registry.url") == "http://localhost:8000"
        finally:
            # Clean up the temporary file
            Path(config_path).unlink()
    
    def test_environment_overrides_file(self) -> None:
        """Test that environment variables override file configuration."""
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "mode": "DEV",
                "encryption": {
                    "enabled": False
                }
            }, f)
            config_path = f.name
        
        try:
            # Set an environment variable that conflicts with the file
            os.environ["INDALEKO_MODE"] = "PROD"
            
            # Initialize with the config file
            DBFacadeConfig.initialize(config_path)
            
            # The environment variable should take precedence
            assert DBFacadeConfig.get("mode") == "PROD"
            
            # Other values from the file should be used
            assert DBFacadeConfig.get("encryption.enabled") is False
        finally:
            # Clean up the temporary file
            Path(config_path).unlink()
    
    def test_config_helpers(self) -> None:
        """Test the helper methods for commonly used configuration values."""
        # Set up a test configuration
        os.environ["INDALEKO_MODE"] = "PROD"
        os.environ["INDALEKO_ENCRYPTION_ENABLED"] = "true"
        
        # Re-initialize the configuration
        DBFacadeConfig.initialize()
        
        # Test the helper methods
        assert DBFacadeConfig.is_dev_mode() is False
        assert DBFacadeConfig.is_encryption_enabled() is True
        assert DBFacadeConfig.get_registry_url() == "http://localhost:8000"
        assert DBFacadeConfig.get_database_url() == "http://localhost:8529"