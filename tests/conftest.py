"""
Pytest configuration for DB Facade tests.
"""

import os
import pytest
from typing import Dict, Any, Generator


@pytest.fixture
def dev_mode_env() -> Generator[None, None, None]:
    """
    Set up environment for development mode testing.
    
    This fixture ensures that the INDALEKO_MODE environment variable
    is set to 'DEV' during the test, and then restores the original
    value afterward.
    """
    original_mode = os.environ.get("INDALEKO_MODE")
    os.environ["INDALEKO_MODE"] = "DEV"
    
    yield
    
    if original_mode is not None:
        os.environ["INDALEKO_MODE"] = original_mode
    else:
        del os.environ["INDALEKO_MODE"]


@pytest.fixture
def prod_mode_env() -> Generator[None, None, None]:
    """
    Set up environment for production mode testing.
    
    This fixture ensures that the INDALEKO_MODE environment variable
    is set to 'PROD' during the test, and then restores the original
    value afterward.
    """
    original_mode = os.environ.get("INDALEKO_MODE")
    os.environ["INDALEKO_MODE"] = "PROD"
    
    yield
    
    if original_mode is not None:
        os.environ["INDALEKO_MODE"] = original_mode
    else:
        del os.environ["INDALEKO_MODE"]


@pytest.fixture
def mock_registry_data() -> Dict[str, Any]:
    """
    Provide mock registry mapping data for testing.
    
    This fixture returns a dictionary mapping semantic field names to UUIDs
    that can be used for testing without requiring the actual registry service.
    """
    return {
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "email": "234e5678-e89b-12d3-a456-426614174000",
        "name": "345e6789-e89b-12d3-a456-426614174000",
        "address": "456e7890-e89b-12d3-a456-426614174000",
        "phone": "567e8901-e89b-12d3-a456-426614174000",
        "Users": "678e9012-e89b-12d3-a456-426614174000",
        "Accounts": "789e0123-e89b-12d3-a456-426614174000",
    }