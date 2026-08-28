"""
Shared database accessor. Import this instead of calling PersistenceService directly.

Usage:
    from app.db import db
    conn = db()
"""

from app.services.db_adapters import DatabaseAdapter
from app.services.persistence import PersistenceService

db = PersistenceService.get_db
get_table = PersistenceService.get_table

__all__ = ["DatabaseAdapter", "PersistenceService", "db", "get_table"]
