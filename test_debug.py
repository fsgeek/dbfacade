#!/usr/bin/env python3
"""Debug script to examine database structure"""

import os
import sys
from indaleko_dbfacade.config import DBFacadeConfig
from indaleko_dbfacade.db.arangodb import ArangoDBClient

# Set up config
secrets_file = os.path.join(".secrets", "db_config.yaml")
DBFacadeConfig.initialize()
DBFacadeConfig.load_from_secrets_file(secrets_file)

# Create database client
db = ArangoDBClient(registry_collection="test_registry", data_collection="test_data")

# Query all documents in test_data collection
query = """
FOR doc IN test_data
LIMIT 5
RETURN doc
"""

print("Test data documents:")
cursor = db.db.aql.execute(query)
for doc in cursor:
    print(doc)

print("\nRegistry documents:")
query = """
FOR doc IN test_registry
LIMIT 10
RETURN doc
"""

cursor = db.db.aql.execute(query)
for doc in cursor:
    print(doc)