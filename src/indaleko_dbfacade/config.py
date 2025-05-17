"""
Configuration management for DB Facade.

This module provides configuration utilities for controlling behavior
of the DB Facade service, including development/production modes and
encryption settings.
"""

import os
import sys
from pathlib import Path
from copy import deepcopy
# No need for typing imports in Python 3.13

import yaml


class DBFacadeConfig:
    """
    Configuration for the DB Facade.
    
    This class provides access to configuration settings, including
    environment-specific behaviors and encryption settings.
    """
    
    # Default configuration values
    _default_config: dict[str, object] = {
        "mode": "DEV",  # DEV or PROD
        "encryption": {
            "enabled": False,
            "algorithm": "AES-GCM",
            "key_derivation": "PBKDF2",
        },
        "registry": {
            "url": "http://localhost:8000",
            "cache_ttl": 3600,  # seconds
        },
        "database": {
            "url": "http://localhost:8529",
            "database": "dbfacade",
            "username": "root",
            "password": "",
        },
    }
    
    # Instance configuration values, loaded from file or environment
    _config: dict[str, object] = {}
    
    # Flag indicating if the configuration has been initialized
    _initialized: bool = False
    
    @classmethod
    def initialize(cls, config_path: str | None = None) -> None:
        """
        Initialize the configuration.
        
        Args:
            config_path: Optional path to a YAML configuration file
        """
        # Start with default configuration (deep copy to avoid shared nested dictionaries)
        cls._config = deepcopy(cls._default_config)
        
        # Load configuration from file if provided
        if config_path:
            cls._load_from_file(config_path)
        
        # Override with environment variables
        cls._load_from_env()
        
        # Mark as initialized
        cls._initialized = True
    
    @classmethod
    def _load_from_file(cls, config_path: str) -> None:
        """
        Load configuration from a YAML file.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        path = Path(config_path)
        if not path.exists():
            print(f"Configuration file not found: {config_path}")
            sys.exit(1)
        
        try:
            with open(path, "r") as f:
                file_config = yaml.safe_load(f)
                
            # Update configuration with values from file
            if file_config:
                cls._config.update(file_config)
        except Exception as e:
            print(f"Error loading configuration file: {e}")
            sys.exit(1)
    
    @classmethod
    def _load_from_env(cls) -> None:
        """Load configuration from environment variables."""
        # Check for mode override
        env_mode = os.environ.get("INDALEKO_MODE")
        if env_mode in ("DEV", "PROD"):
            cls._config["mode"] = env_mode
        
        # Check for encryption enabled override
        env_encryption = os.environ.get("INDALEKO_ENCRYPTION_ENABLED")
        if env_encryption in ("1", "true", "True", "yes", "Yes"):
            cls._config["encryption"]["enabled"] = True
        elif env_encryption in ("0", "false", "False", "no", "No"):
            cls._config["encryption"]["enabled"] = False
        
        # Check for database URL override
        env_db_url = os.environ.get("INDALEKO_DB_URL")
        if env_db_url:
            cls._config["database"]["url"] = env_db_url
        
        # Check for database username override
        env_db_username = os.environ.get("INDALEKO_DB_USERNAME")
        if env_db_username:
            cls._config["database"]["username"] = env_db_username
        
        # Check for database password override
        env_db_password = os.environ.get("INDALEKO_DB_PASSWORD")
        if env_db_password:
            cls._config["database"]["password"] = env_db_password
        
        # Check for registry URL override
        env_registry_url = os.environ.get("INDALEKO_REGISTRY_URL")
        if env_registry_url:
            cls._config["registry"]["url"] = env_registry_url
    
    @classmethod
    def _ensure_initialized(cls) -> None:
        """Ensure the configuration is initialized."""
        if not cls._initialized:
            cls.initialize()
    
    @classmethod
    def get(cls, key: str, default: object = None) -> object:
        """
        Get a configuration value.
        
        Args:
            key: The configuration key to retrieve
            default: Default value to return if key is not found
            
        Returns:
            The configuration value, or default if not found
        """
        cls._ensure_initialized()
        
        # Support nested keys with dot notation
        if "." in key:
            parts = key.split(".")
            value = cls._config
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value
        
        return cls._config.get(key, default)
    
    @classmethod
    def is_dev_mode(cls) -> bool:
        """
        Check if the system is in development mode.
        
        Returns:
            True if in development mode, False otherwise
        """
        return cls.get("mode") == "DEV"
    
    @classmethod
    def is_encryption_enabled(cls) -> bool:
        """
        Check if encryption is enabled.
        
        Returns:
            True if encryption is enabled, False otherwise
        """
        return cls.get("encryption.enabled", False)
    
    @classmethod
    def get_registry_url(cls) -> str:
        """
        Get the registry service URL.
        
        Returns:
            The URL of the registry service
        """
        return cls.get("registry.url", "http://localhost:8000")
    
    @classmethod
    def get_database_url(cls) -> str:
        """
        Get the database URL.
        
        Returns:
            The URL of the database
        """
        return cls.get("database.url", "http://localhost:8529")
    
    @classmethod
    def get_database_credentials(cls) -> dict:
        """
        Get the database credentials.
        
        Returns:
            Dictionary containing database credentials
        """
        return {
            "username": cls.get("database.username", "root"),
            "password": cls.get("database.password", ""),
            "database": cls.get("database.database", "dbfacade")
        }
    
    @classmethod
    def load_from_secrets_file(cls, file_path: str) -> None:
        """
        Load configuration from a secrets file.
        
        This is a convenience method for loading configuration from
        a secrets file, which can contain sensitive information.
        
        Args:
            file_path: Path to the secrets file
        """
        path = Path(file_path)
        if not path.exists():
            print(f"Secrets file not found: {file_path}")
            return
        
        try:
            with open(path, "r") as f:
                secrets = yaml.safe_load(f)
                
            # Update configuration with values from secrets
            if secrets:
                for section, values in secrets.items():
                    if isinstance(values, dict):
                        if section not in cls._config:
                            cls._config[section] = {}
                        cls._config[section].update(values)
                    else:
                        cls._config[section] = values
                
            print(f"Loaded configuration from secrets file: {file_path}")
        except Exception as e:
            print(f"Error loading secrets file: {e}")
            sys.exit(1)