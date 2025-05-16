"""
Example of using encrypted fields in obfuscated models.

This example demonstrates how to define and use models with encrypted fields.
"""

import os
import json
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from indaleko_dbfacade.config import DBFacadeConfig
from indaleko_dbfacade.models import ObfuscatedField, ObfuscatedModel
from indaleko_dbfacade.models.obfuscated_model import ObfuscationLevel


# Define an obfuscated model with encrypted fields
class UserWithEncryption(ObfuscatedModel):
    """
    User model with encrypted sensitive fields.
    
    This model demonstrates how to define an obfuscated model with
    encrypted fields for sensitive data.
    """
    
    # Regular fields (will be obfuscated with UUID but not encrypted)
    name: str
    email: str
    
    # Sensitive fields that should be encrypted
    password: str = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
    ssn: Optional[str] = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
    
    # Payment information (also encrypted)
    credit_card: Optional[str] = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
    
    # Non-sensitive field that doesn't need obfuscation
    public_profile: bool = ObfuscatedField(obfuscation_level=ObfuscationLevel.NONE)


def main() -> None:
    """Example usage of encrypted fields in obfuscated models."""
    # Setup environment for the example
    os.environ["INDALEKO_MODE"] = "DEV"
    os.environ["INDALEKO_ENCRYPTION_ENABLED"] = "true"
    os.environ["INDALEKO_ENCRYPTION_KEY"] = "example-master-key-for-demonstration"
    
    # Force re-initialization of configuration
    DBFacadeConfig.initialize()
    
    print("\nEncryption enabled:", DBFacadeConfig.is_encryption_enabled())
    print("Development mode:", DBFacadeConfig.is_dev_mode())
    
    # Create a user with sensitive information
    user = UserWithEncryption.create_from_semantic(
        name="John Doe",
        email="john@example.com",
        password="SecurePassword123!",
        ssn="123-45-6789",
        credit_card="4242-4242-4242-4242",
        public_profile=True
    )
    
    # In development mode, we can see the semantic field names and decrypted values
    print("\nUser model in DEV mode (decrypted for development):")
    print(json.dumps(user.model_dump(), indent=2))
    
    # Switch to production mode
    os.environ["INDALEKO_MODE"] = "PROD"
    DBFacadeConfig.initialize()
    
    # In production mode, we'll see UUID keys and encrypted values
    print("\nUser model in PROD mode (encrypted sensitive fields):")
    
    # Get the raw data representation
    raw_data = user.model_dump()
    
    # Pretty-print with some formatting for clarity
    for key, value in raw_data.items():
        if isinstance(value, dict) and "metadata" in value:
            print(f"{key}: <encrypted value>")
            print(f"  Algorithm: {value['metadata']['algorithm']}")
            print(f"  Created: {value['metadata']['created_at']}")
        else:
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()