# DB Facade Design Document

## 1. Overview and Goals

DB Facade is a database obfuscation layer that protects against third-party data service provider compromise by:

1. Automatically mapping semantically meaningful names to meaningless UUIDs
2. Separating the database from the mapping layer (using two separate databases)
3. Reducing developer friction by providing semantic name resolution in development environments
4. Supporting data encryption in production environments

## 2. Architecture

### 2.1 System Components

The system consists of the following key components:

1. **Pydantic Model Layer**
   - Custom base classes that extend Pydantic models
   - Provides automatic field mapping from semantic names to UUIDs
   - Handles serialization/deserialization with proper obfuscation

2. **Registry Service**
   - External service for mapping semantic labels to UUIDs
   - Maintains persistence of mappings in a separate database
   - Provides lookup capabilities in both directions (UUID → label, label → UUID)

3. **DB Facade Service**
   - REST API for database operations
   - Enforces UUID-based access patterns
   - Conditionally resolves UUIDs to semantic names in development mode

4. **Encryption Layer**
   - Handles field-level encryption/decryption
   - Derives encryption keys from master keys and field UUIDs
   - Manages encryption metadata

5. **Configuration Manager**
   - Controls development vs. production behaviors
   - Manages secrets and key access
   - Configures encryption policies

### 2.2 Data Flow

1. **Writing Data**:
   - Application uses semantic field names in Pydantic models
   - Model's `__init__` or custom serializer maps semantic names to UUIDs using Registry Service
   - If encryption is enabled, sensitive fields are encrypted
   - DB Facade Service stores the UUID-mapped (and possibly encrypted) data in the database

2. **Reading Data**:
   - DB Facade Service retrieves UUID-mapped data
   - If encryption is enabled, encrypted fields are decrypted
   - In development mode only, UUIDs are resolved back to semantic names
   - Application receives data with appropriate field names based on environment

## 3. Technical Specifications

### 3.1 Pydantic Model Layer

```python
# Example implementation concept
class ObfuscatedModel(BaseModel):
    """Base class for models with automatic field obfuscation."""
    
    model_config = {
        # Pydantic config to allow UUID field mapping
        "arbitrary_types_allowed": True
    }
        
    def __init__(self, **data):
        # Map semantic fields to UUIDs before initialization
        uuid_data = self._map_to_uuids(data)
        super().__init__(**uuid_data)
    
    def _map_to_uuids(self, data):
        # Use Registry Service to map field names to UUIDs
        # Implementation depends on registry service API
        pass
        
    def model_dump(self, *args, **kwargs):
        # Override to control how the model is serialized
        # For dev mode, can map UUIDs back to semantic names
        uuid_dict = super().model_dump(*args, **kwargs)
        
        if os.getenv("INDALEKO_MODE", "DEV") == "DEV":
            # Use Registry Service to map UUIDs back to semantic names
            return self._map_to_semantic(uuid_dict)
        
        return uuid_dict
```

### 3.2 Registry Service Integration

We'll need interfaces to the existing registry service:

```python
class RegistryClient:
    """Client for interacting with the registry service."""
    
    def get_uuid_for_label(self, label: str) -> UUID:
        """Get or create a UUID for a semantic label."""
        pass
        
    def get_label_for_uuid(self, uuid: UUID) -> str:
        """Get the semantic label for a UUID."""
        pass
        
    def register_model_schema(self, model_class) -> Dict[str, UUID]:
        """Register all fields in a model class and return mapping."""
        pass
```

### 3.3 Encryption Layer

```python
class FieldEncryptor:
    """Handles field-level encryption/decryption."""
    
    def __init__(self, master_key: str):
        self.master_key = master_key
        
    def derive_key(self, field_uuid: UUID) -> bytes:
        """Derive an encryption key for a specific field."""
        pass
        
    def encrypt_field(self, value: Any, field_uuid: UUID) -> Dict[str, Any]:
        """Encrypt a field value."""
        # Returns structure with encrypted value and metadata
        pass
        
    def decrypt_field(self, encrypted_data: Dict[str, Any], field_uuid: UUID) -> Any:
        """Decrypt a field value."""
        pass
```

### 3.4 DB Facade Service (REST API)

The REST API will need to include:

1. Collection management
2. Schema management
3. Batch operations
4. Transaction support
5. Query capabilities with proper UUID translation

### 3.5 Configuration Manager

```python
class DBFacadeConfig:
    """Configuration for the DB Facade."""
    
    def __init__(self, config_path: str = None):
        # Load config from file or environment
        pass
        
    @property
    def is_dev_mode(self) -> bool:
        """Whether the system is in development mode."""
        pass
        
    @property
    def encryption_enabled(self) -> bool:
        """Whether field encryption is enabled."""
        pass
        
    def get_master_key(self) -> str:
        """Get the master encryption key."""
        # Should use secure methods to retrieve key
        pass
```

## 4. Security Considerations

1. **Separation of Concerns**:
   - Registry database and data database should be physically separated
   - Access controls should differ for each database
   - In production, only the application should have access to both databases

2. **Key Management**:
   - Encryption keys should never be stored with the data
   - Consider using a dedicated key management service (KMS)
   - Key rotation should be supported

3. **Development Mode Safeguards**:
   - Development mode should be clearly indicated in the UI/API
   - Production environments should have development mode disabled in configuration
   - Consider adding safeguards against accidentally enabling development mode in production

4. **Audit Logging**:
   - All operations that reveal semantic information should be logged
   - Access to the registry service should be audited
   - Failed mapping attempts should trigger alerts

## 5. Integration with Existing Systems

### 5.1 Registry Service Integration

The existing registry service will be integrated with the DB Facade:

1. Import the registry client library
2. Configure connection parameters
3. Ensure proper error handling for registry service failures

### 5.2 Database Backend

The system supports two databases:

1. **Mapping Database**:
   - Used by registry service to store label → UUID mappings
   - Should be secured separately from the data database

2. **Data Database**:
   - Stores the actual obfuscated data
   - Contains no semantic information
   - May contain encrypted fields