"""
QuakeSense Database Package
Provides database abstraction and management for seismic event storage
"""

from .db_manager import DatabaseManager, get_database

__all__ = ['DatabaseManager', 'get_database']
