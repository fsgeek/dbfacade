#!/usr/bin/env python3
"""
DB Facade Service entry point.

This script starts the DB Facade Service API server or demonstrates
the DB Facade Service in action based on command line arguments.
"""

import argparse
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from indaleko_dbfacade.config import DBFacadeConfig
from indaleko_dbfacade.service import start_api
from indaleko_dbfacade.db_facade_service import DBFacadeService
from indaleko_dbfacade.models.obfuscated_model import ObfuscatedModel
from pydantic import BaseModel, Field


# Example models for demonstration
class UserProfile(ObfuscatedModel):
    """Example user profile model for demonstration."""
    
    username: str
    email: str
    full_name: str
    age: int
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)


class ActivityRecord(ObfuscatedModel):
    """Example activity record model for demonstration."""
    
    user_id: uuid.UUID
    action: str
    resource: str
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Dict[str, Any] = Field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="DB Facade Service")
    
    # API server options
    parser.add_argument(
        "--host", 
        default="0.0.0.0", 
        help="Host to bind to (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port to bind to (default: 8000)"
    )
    
    parser.add_argument(
        "--config", 
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--mode", 
        choices=["DEV", "PROD"], 
        help="Override operation mode (DEV or PROD)"
    )
    
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="Enable auto-reload for development"
    )
    
    # Demo options
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a demonstration of the DB Facade Service"
    )
    
    parser.add_argument(
        "--demo-create",
        action="store_true",
        help="Create example records in the database"
    )
    
    parser.add_argument(
        "--demo-query",
        action="store_true",
        help="Query example records from the database"
    )
    
    return parser.parse_args()


def run_demo_create() -> None:
    """Run a demonstration of creating records with the DB Facade Service."""
    print("Running DB Facade Service creation demo...")
    
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
    
    # Create an activity record
    activity = ActivityRecord(
        user_id=user_uuid,
        action="login",
        resource="webapp",
        details={"ip": "192.168.1.1", "browser": "Firefox"}
    )
    
    # Store the activity record
    activity_uuid = service.store_model(activity)
    print(f"Created activity record with UUID: {activity_uuid}")
    
    print("Creation demo completed successfully!")


def run_demo_query() -> None:
    """Run a demonstration of querying records with the DB Facade Service."""
    print("Running DB Facade Service query demo...")
    
    # Initialize the DB Facade Service
    service = DBFacadeService()
    
    # Query user profiles
    try:
        users = service.query_models(
            UserProfile,
            {"username": "jdoe"},
            limit=10
        )
        
        print(f"Found {len(users)} user profiles:")
        for i, user in enumerate(users):
            print(f"  User {i+1}:")
            print(f"    Username: {user.username}")
            print(f"    Email: {user.email}")
            print(f"    Full Name: {user.full_name}")
            print(f"    Age: {user.age}")
            print(f"    Active: {user.is_active}")
            print(f"    Created At: {user.created_at}")
            
            # Get activity records for this user
            try:
                user_id = user.id if hasattr(user, 'id') else uuid.UUID("00000000-0000-0000-0000-000000000000")
                activities = service.query_models(
                    ActivityRecord,
                    {"user_id": user_id},
                    limit=5
                )
                
                print(f"  Recent Activities ({len(activities)}):")
                for j, activity in enumerate(activities):
                    print(f"    Activity {j+1}:")
                    print(f"      Action: {activity.action}")
                    print(f"      Resource: {activity.resource}")
                    print(f"      Timestamp: {activity.timestamp}")
                    print(f"      Details: {activity.details}")
            except Exception as e:
                print(f"  Error querying activities: {e}")
    except Exception as e:
        print(f"Error querying users: {e}")
    
    print("Query demo completed!")


def main() -> None:
    """Main entry point for the DB Facade Service."""
    args = parse_args()
    
    # Set environment variables from command line
    if args.mode:
        os.environ["INDALEKO_MODE"] = args.mode
    
    # Initialize configuration
    DBFacadeConfig.initialize()
    
    # Load config file if provided
    if args.config:
        DBFacadeConfig._load_from_file(args.config)
    
    # Look for secrets file in standard location
    secrets_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".secrets", "db_config.yaml")
    if os.path.exists(secrets_file):
        DBFacadeConfig.load_from_secrets_file(secrets_file)
    
    # Print startup information
    mode = DBFacadeConfig.get("mode")
    print(f"DB Facade Service - {mode} mode")
    print(f"Encryption enabled: {DBFacadeConfig.is_encryption_enabled()}")
    
    # Run a demo if requested
    if args.demo or args.demo_create or args.demo_query:
        if args.demo or args.demo_create:
            run_demo_create()
        
        if args.demo or args.demo_query:
            run_demo_query()
        
        return
    
    # Otherwise, start the API server
    print(f"Starting API server on {args.host}:{args.port}")
    
    try:
        start_api(host=args.host, port=args.port, reload=args.reload)
    except KeyboardInterrupt:
        print("Service stopped")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting service: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
