"""
Module: core.storage
Factory for pluggable storage backends.
"""

from database.mongodb import MongoDatabase
# from core.database.redis import RedisDatabase  # Placeholder for future backends

from config import (
    DATABASE_TYPE, 
    MONGODB_HOST, MONGODB_PORT, MONGODB_DATABASE, 
    MONGODB_USERNAME, MONGODB_PASSWORD,

)

def get_storage(db_name: str = MONGODB_DATABASE):
    """Return DatabaseInterface implementation based on config.DATABASE_TYPE."""

    if DATABASE_TYPE.lower() == "mongodb":
        if MONGODB_USERNAME and MONGODB_PASSWORD:
            uri = f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}"
        else:
            uri = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}"
        
        return MongoDatabase(uri=uri, db_name=db_name)
    
    # elif DATABASE_TYPE.lower() == "redis":
    #     return RedisDatabase(...)

    raise ValueError(f"Unsupported DATABASE_TYPE: {DATABASE_TYPE}")
