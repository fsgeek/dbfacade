# DB Facade

DB Facade is a database obfuscation layer that provides the following features:

* Ensures that field names and collection names in the database are obscured with UUIDs
* Minimizes developer friction by mapping between UUIDs and semantic names in development mode
* Separates the database from the mapping layer
* Supports field-level data encryption in production environments
* Implements a strict fail-stop approach to error handling

## Requirements

To use this package requires:

* Python 3.9+ (tested on 3.9, 3.10, 3.11, 3.12, 3.13)
* Pydantic v2 for data validation and serialization
* ArangoDB for database storage
* A secure mechanism for managing encryption keys and secrets

## Installation

```bash
# Install from source
pip install -e .

# For development, install test dependencies
pip install -e ".[dev]"
```

## Quick Start

### 1. Define an Obfuscated Model

```python
from indaleko_dbfacade.models import ObfuscatedModel
from pydantic import Field
from datetime import datetime
import uuid

class UserProfile(ObfuscatedModel):
    username: str
    email: str
    full_name: str
    age: int
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
```

### 2. Store Data in the Database

```python
from indaleko_dbfacade.db_facade_service import DBFacadeService

# Initialize the DB Facade Service
service = DBFacadeService()

# Create a user profile
user = UserProfile(
    username="jdoe",
    email="john.doe@example.com",
    full_name="John Doe",
    age=32
)

# Store the user profile
user_uuid = service.store_model(user)
print(f"Created user profile with UUID: {user_uuid}")
```

### 3. Query Data from the Database

```python
# Query user profiles
users = service.query_models(
    UserProfile,
    {"username": "jdoe"},
    limit=10
)

print(f"Found {len(users)} user profiles:")
for user in users:
    print(f"Username: {user.username}")
    print(f"Email: {user.email}")
    print(f"Full Name: {user.full_name}")
```

### 4. Run the API Server

```bash
# Start the API server in development mode
python main.py --mode DEV

# Start the API server in production mode
python main.py --mode PROD
```

### 5. Run the Demo

```bash
# Run the full demo (create and query)
python main.py --demo

# Only create example records
python main.py --demo-create

# Only query example records
python main.py --demo-query
```

## Architecture

The DB Facade system consists of the following components:

### Core Components

1. **ObfuscatedModel**: A Pydantic-based model that automatically maps semantic field names to UUIDs.

2. **Registry Service**: Maintains mappings between semantic names and UUIDs.

3. **DB Facade Service**: Provides a high-level interface for database operations with obfuscation.

4. **ArangoDB Client**: Handles low-level database operations with ArangoDB.

5. **Field Encryptor**: Provides field-level encryption for sensitive data.

### Design Principles

The design is built on these key principles:

* **Obfuscation**: Field names and collection names are stored as UUIDs in the database.
* **Mapping Layer**: A registry service maintains mappings between semantic names and UUIDs.
* **Development Mode**: In development mode, UUIDs are mapped back to semantic names for easier debugging.
* **Encryption**: Sensitive fields can be encrypted using field-level encryption.
* **Fail-Stop Approach**: Errors are never masked; the system fails immediately when issues occur.

#### Data Flow

1. **Storage**:
   - Model fields are mapped to UUIDs
   - Field values are optionally encrypted
   - Data is stored in the database with UUID keys

2. **Retrieval**:
   - Data is retrieved from the database with UUID keys
   - UUIDs are mapped back to semantic names in development mode
   - Encrypted values are decrypted

## Configuration

Configuration is managed through environment variables or a YAML configuration file:

```yaml
# config.yaml
mode: "DEV"  # DEV or PROD
encryption:
  enabled: true
  algorithm: "AES-GCM"
  key_derivation: "PBKDF2"
registry:
  url: "http://localhost:8000"
  cache_ttl: 3600
database:
  url: "http://localhost:8529"
  database: "dbfacade"
  username: "root"
  password: ""
```

Or through environment variables:

```bash
# Set mode to production
export INDALEKO_MODE=PROD

# Enable encryption
export INDALEKO_ENCRYPTION_ENABLED=true

# Set database URL
export INDALEKO_DB_URL=http://db.example.com:8529
```

## Security Considerations

- In production mode, all semantic field names are obfuscated in the database
- Registry collection should be secured with appropriate access controls
- Encryption keys should be securely managed using a key management system
- Follow the principle of least privilege for database access
- Consider physical isolation of the registry and data databases
- Regularly rotate encryption keys and audit access patterns

## Testing

Run the test suite to verify correct functionality:

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/models/
pytest tests/encryption/
pytest tests/service/

# Run with coverage
pytest --cov=indaleko_dbfacade
```

## Troubleshooting

The system follows a strict fail-stop approach to error handling. If you encounter errors:

1. Check database connectivity using the health endpoint
2. Verify that collections exist in the database
3. Ensure encryption keys are properly configured (if encryption is enabled)
4. Check for detailed error messages in development mode
5. Review the logs for more information

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to the project.
