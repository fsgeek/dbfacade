"""
Field encryption implementation.

This module provides the core encryption functionality for securing
sensitive fields in database models.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union, cast
from uuid import UUID

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..config import DBFacadeConfig


class EncryptionAlgorithm(str, Enum):
    """Supported encryption algorithms."""
    
    AES_GCM = "AES-GCM"
    CHACHA20_POLY1305 = "ChaCha20-Poly1305"


@dataclass
class EncryptionMetadata:
    """
    Metadata for an encrypted field.
    
    This contains information needed to decrypt the field, such as
    the algorithm used and initialization vector.
    """
    
    # Encryption algorithm used
    algorithm: EncryptionAlgorithm
    
    # Initialization vector or nonce
    iv: str
    
    # Salt used for key derivation
    salt: str
    
    # When the field was encrypted
    created_at: str
    
    # Version of the encryption format
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, str]:
        """
        Convert metadata to a dictionary for storage.
        
        Returns:
            Dictionary representation of the metadata
        """
        return {
            "algorithm": self.algorithm.value,
            "iv": self.iv,
            "salt": self.salt,
            "created_at": self.created_at,
            "version": self.version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "EncryptionMetadata":
        """
        Create metadata from a dictionary.
        
        Args:
            data: Dictionary containing metadata fields
            
        Returns:
            EncryptionMetadata instance
        """
        return cls(
            algorithm=EncryptionAlgorithm(data["algorithm"]),
            iv=data["iv"],
            salt=data["salt"],
            created_at=data["created_at"],
            version=data.get("version", "1.0"),
        )


class FieldEncryptor:
    """
    Handles field-level encryption and decryption.
    
    This class provides methods for encrypting and decrypting individual
    field values, using a master key and field UUID to derive unique
    encryption keys for each field.
    """
    
    def __init__(self, master_key: Optional[str] = None) -> None:
        """
        Initialize the field encryptor.
        
        Args:
            master_key: Optional master encryption key
        """
        self.master_key = master_key or self._get_master_key()
        
        # Verify we have a master key
        if not self.master_key:
            print("ERROR: No master encryption key provided or found in environment", file=sys.stderr)
            sys.exit(1)
            
        # Default algorithm
        self.default_algorithm = DBFacadeConfig.get(
            "encryption.algorithm", EncryptionAlgorithm.AES_GCM.value
        )
        
        # Key derivation parameters
        self.key_iterations = DBFacadeConfig.get("encryption.key_iterations", 100000)
    
    def _get_master_key(self) -> str:
        """
        Get the master encryption key from configuration or environment.
        
        Returns:
            The master key as a string
        """
        # Try to get from environment variable
        key = os.environ.get("INDALEKO_ENCRYPTION_KEY")
        if key:
            return key
            
        # Try to get from config
        key = DBFacadeConfig.get("encryption.key")
        if key:
            return key
            
        # Check if we're in development mode and can use a default key
        if DBFacadeConfig.is_dev_mode():
            return "dev-only-encryption-key-do-not-use-in-production"
            
        # No key found
        return ""
    
    def derive_key(self, field_uuid: UUID, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        Derive an encryption key for a specific field.
        
        This uses PBKDF2 to derive a unique key for each field based on
        the master key and the field's UUID.
        
        Args:
            field_uuid: UUID of the field
            salt: Optional salt for key derivation
            
        Returns:
            Tuple of (derived key, salt used)
        """
        # Generate a salt if not provided
        if salt is None:
            salt = os.urandom(16)
            
        # Convert master key to bytes
        master_key_bytes = self.master_key.encode("utf-8")
        
        # Mix in the field UUID
        field_specific_key = hashlib.sha256(
            master_key_bytes + str(field_uuid).encode("utf-8")
        ).digest()
        
        # Derive the key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=salt,
            iterations=self.key_iterations,
            backend=default_backend(),
        )
        key = kdf.derive(field_specific_key)
        
        return key, salt
    
    def encrypt_field(
        self, 
        value: Any, 
        field_uuid: UUID, 
        algorithm: Optional[EncryptionAlgorithm] = None
    ) -> Dict[str, Any]:
        """
        Encrypt a field value.
        
        Args:
            value: The value to encrypt
            field_uuid: UUID of the field
            algorithm: Optional encryption algorithm to use
            
        Returns:
            Dictionary containing the encrypted value and metadata
        """
        # Use default algorithm if not specified
        if algorithm is None:
            algorithm = EncryptionAlgorithm(self.default_algorithm)
            
        # Serialize the value to JSON
        value_json = json.dumps(value)
        value_bytes = value_json.encode("utf-8")
        
        # Generate a salt and derive a key
        salt = os.urandom(16)
        key, _ = self.derive_key(field_uuid, salt)
        
        # Generate a nonce/iv
        iv = os.urandom(12)  # 96-bit IV for GCM mode
        
        # Encrypt the value
        if algorithm == EncryptionAlgorithm.AES_GCM:
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),
                backend=default_backend(),
            )
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(value_bytes) + encryptor.finalize()
            
            # Combine ciphertext and tag
            encrypted_data = ciphertext + encryptor.tag
        else:
            # Implement other algorithms as needed
            raise ValueError(f"Unsupported encryption algorithm: {algorithm}")
            
        # Create metadata
        metadata = EncryptionMetadata(
            algorithm=algorithm,
            iv=base64.b64encode(iv).decode("utf-8"),
            salt=base64.b64encode(salt).decode("utf-8"),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # Return encrypted value and metadata
        return {
            "value": base64.b64encode(encrypted_data).decode("utf-8"),
            "metadata": metadata.to_dict(),
        }
    
    def decrypt_field(self, encrypted_data: Dict[str, Any], field_uuid: UUID) -> Any:
        """
        Decrypt a field value.
        
        Args:
            encrypted_data: Dictionary containing encrypted value and metadata
            field_uuid: UUID of the field
            
        Returns:
            The decrypted value
        """
        # Check if we have the necessary data
        if "value" not in encrypted_data or "metadata" not in encrypted_data:
            raise ValueError("Invalid encrypted data format")
            
        # Parse the metadata
        metadata = EncryptionMetadata.from_dict(
            cast(Dict[str, str], encrypted_data["metadata"])
        )
        
        # Decode the encrypted value
        encrypted_value = base64.b64decode(encrypted_data["value"])
        
        # Decode the IV and salt
        iv = base64.b64decode(metadata.iv)
        salt = base64.b64decode(metadata.salt)
        
        # Derive the key
        key, _ = self.derive_key(field_uuid, salt)
        
        # Decrypt the value
        if metadata.algorithm == EncryptionAlgorithm.AES_GCM:
            # Split ciphertext and tag
            ciphertext = encrypted_value[:-16]
            tag = encrypted_value[-16:]
            
            # Create the cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, tag),
                backend=default_backend(),
            )
            decryptor = cipher.decryptor()
            decrypted_bytes = decryptor.update(ciphertext) + decryptor.finalize()
        else:
            # Implement other algorithms as needed
            raise ValueError(f"Unsupported encryption algorithm: {metadata.algorithm}")
            
        # Deserialize the value from JSON
        decrypted_value = json.loads(decrypted_bytes.decode("utf-8"))
        
        return decrypted_value
    
    def encrypt_value(self, value: Any, field_uuid: UUID) -> str:
        """
        Encrypt a value and return as a JSON string.
        
        This is a convenience method that encrypts a value and returns
        the result as a JSON string, suitable for storage in a database.
        
        Args:
            value: The value to encrypt
            field_uuid: UUID of the field
            
        Returns:
            JSON string containing the encrypted value and metadata
        """
        encrypted_data = self.encrypt_field(value, field_uuid)
        return json.dumps(encrypted_data)
    
    def decrypt_value(self, encrypted_json: str, field_uuid: UUID) -> Any:
        """
        Decrypt a value from a JSON string.
        
        This is a convenience method that decrypts a value from a JSON
        string, as returned by encrypt_value.
        
        Args:
            encrypted_json: JSON string containing encrypted value and metadata
            field_uuid: UUID of the field
            
        Returns:
            The decrypted value
        """
        encrypted_data = json.loads(encrypted_json)
        return self.decrypt_field(encrypted_data, field_uuid)