"""
DB Facade Service API.

This module provides the REST API for the DB Facade service, allowing
clients to interact with the database using obfuscated field names.
"""

from .api import app, start_api, submit_record, run_query, get_record

__all__ = ["app", "start_api", "submit_record", "run_query", "get_record"]