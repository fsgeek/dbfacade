#!/usr/bin/env python3
"""
DB Facade Service entry point.

This script starts the DB Facade Service API server.
"""

import argparse
import os
import sys

from indaleko_dbfacade.config import DBFacadeConfig
from indaleko_dbfacade.service import start_api


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="DB Facade Service")
    
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
    
    return parser.parse_args()


def main() -> None:
    """Main entry point for the DB Facade Service."""
    args = parse_args()
    
    # Set environment variables from command line
    if args.mode:
        os.environ["INDALEKO_MODE"] = args.mode
    
    # Initialize configuration
    if args.config:
        DBFacadeConfig.initialize(args.config)
    else:
        DBFacadeConfig.initialize()
    
    # Print startup information
    mode = DBFacadeConfig.get("mode")
    print(f"Starting DB Facade Service in {mode} mode")
    print(f"Encryption enabled: {DBFacadeConfig.is_encryption_enabled()}")
    print(f"Listening on {args.host}:{args.port}")
    
    # Start the API server
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
