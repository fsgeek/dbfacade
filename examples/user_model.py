"""
Example usage of the ObfuscatedModel class.

This example shows how to define and use obfuscated models for database storage.
"""

import os
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from indaleko_dbfacade.config import DBFacadeConfig
from indaleko_dbfacade.models import ObfuscatedField, ObfuscatedModel
from indaleko_dbfacade.models.obfuscated_model import ObfuscationLevel


# Define an obfuscated model for User data
class User(ObfuscatedModel):
    """
    User model with obfuscated fields.
    
    This model demonstrates how to define an obfuscated model with a mix
    of regular and sensitive fields.
    """
    
    # Regular fields (will be obfuscated with UUID but not encrypted)
    name: str
    email: str
    
    # Sensitive field that should be encrypted
    password: str = ObfuscatedField(obfuscation_level=ObfuscationLevel.ENCRYPTED)
    
    # Non-sensitive field that doesn't need obfuscation
    public_profile: bool = ObfuscatedField(
        obfuscation_level=ObfuscationLevel.NONE,
        description="Whether the user's profile is public"
    )
    
    # Optional fields
    bio: Optional[str] = None
    
    # List fields
    roles: List[str] = Field(default_factory=list)


def main() -> None:
    """Example usage of the User model."""
    # Set development mode for this example
    os.environ["INDALEKO_MODE"] = "DEV"
    
    # Force re-initialization of configuration
    DBFacadeConfig.initialize()
    
    # Create a user with semantic field names
    user = User.create_from_semantic(
        name="John Doe",
        email="john@example.com",
        password="Secret123!",
        public_profile=True,
        bio="Software engineer and hobbyist photographer",
        roles=["user", "admin"]
    )
    
    # In development mode, we can see the semantic field names
    print("\nUser model in DEV mode:")
    print(user.model_dump())
    
    # Switch to production mode
    os.environ["INDALEKO_MODE"] = "PROD"
    DBFacadeConfig.initialize()
    
    # In production mode, we'll see UUID keys
    print("\nUser model in PROD mode:")
    print(user.model_dump())
    
    # Register the model schema (creates UUID mappings for all fields)
    mapping = User._register_model_schema()
    print("\nUUID Mappings:")
    for field, uuid in mapping.items():
        print(f"{field}: {uuid}")


if __name__ == "__main__":
    main()