"""
Example API client for the DB Facade Service.

This example demonstrates how to use the DB Facade Service API to
interact with the database using obfuscated field names.
"""

import json
import os
import requests
import uuid
from typing import Dict, Any, List

from indaleko_dbfacade.config import DBFacadeConfig
from indaleko_dbfacade.models import ObfuscatedModel


# Example model using ObfuscatedModel
class Product(ObfuscatedModel):
    """Example product model with obfuscated fields."""
    
    name: str
    price: float
    description: str
    in_stock: bool


def main() -> None:
    """Example usage of the DB Facade Service API."""
    # Configure the API
    api_url = "http://localhost:8000"
    
    print("DB Facade Service API Example\n")
    
    # Check if the API is running
    try:
        response = requests.get(f"{api_url}/health")
        if response.status_code != 200:
            print(f"API is not available at {api_url}")
            return
            
        health_data = response.json()
        print(f"API is running in {health_data['mode']} mode")
    except requests.exceptions.RequestException:
        print(f"API is not available at {api_url}")
        return
    
    # Register a collection UUID
    # In a real application, this would come from the registry service
    collection_uuid = uuid.uuid4()
    print(f"\nUsing collection UUID: {collection_uuid}")
    
    # Create a product with semantic field names
    product = Product.create_from_semantic(
        name="Smartphone",
        price=999.99,
        description="Latest model smartphone with advanced features",
        in_stock=True
    )
    
    # Get the UUID-mapped data for the product
    product_data = product.model_dump()
    print("\nProduct with UUID-mapped fields:")
    print(json.dumps(product_data, indent=2))
    
    # Submit the product to the database
    try:
        response = requests.post(
            f"{api_url}/record",
            json={
                "collection": str(collection_uuid),
                "data": product_data
            }
        )
        
        if response.status_code == 200:
            record_data = response.json()
            record_uuid = record_data["record_uuid"]
            print(f"\nProduct saved with record UUID: {record_uuid}")
        else:
            print(f"\nFailed to save product: {response.json()}")
            return
    except requests.exceptions.RequestException as e:
        print(f"\nFailed to save product: {e}")
        return
    
    # Query for the product
    try:
        # Create a filter with a UUID field
        # For this example, we'll use a dummy filter
        filter_uuid = list(product_data.keys())[0]  # First field UUID
        filter_value = product_data[filter_uuid]
        
        response = requests.post(
            f"{api_url}/query",
            json={
                "collection": str(collection_uuid),
                "filter": {filter_uuid: filter_value},
                "limit": 10,
                "dev_mode": True  # Get semantic field names in response
            }
        )
        
        if response.status_code == 200:
            query_result = response.json()
            print("\nQuery results:")
            print(json.dumps(query_result["results"], indent=2))
            
            if query_result["resolved_fields"]:
                print("\nResolved fields (dev mode only):")
                print(json.dumps(query_result["resolved_fields"], indent=2))
        else:
            print(f"\nFailed to query products: {response.json()}")
            return
    except requests.exceptions.RequestException as e:
        print(f"\nFailed to query products: {e}")
        return
    
    # Get the product by UUID
    try:
        response = requests.get(
            f"{api_url}/record/{record_uuid}?collection={collection_uuid}&dev_mode=true"
        )
        
        if response.status_code == 200:
            record = response.json()
            print("\nRetrieved product:")
            print(json.dumps(record, indent=2))
        else:
            print(f"\nFailed to get product: {response.json()}")
            return
    except requests.exceptions.RequestException as e:
        print(f"\nFailed to get product: {e}")
        return


if __name__ == "__main__":
    main()