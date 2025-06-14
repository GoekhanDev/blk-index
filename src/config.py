import os
from dotenv import load_dotenv

"""
    Load environment variables from .env file
"""

load_dotenv()

def str_to_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes", "on")

DATABASE_TYPE = os.getenv("DATABASE_TYPE", "mongodb")

MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", 27017))
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")

BITCOIN_RPC_HOST = os.getenv("BITCOIN_RPC_HOST")
BITCOIN_RPC_PORT = int(os.getenv("BITCOIN_RPC_PORT", 0)) if os.getenv("BITCOIN_RPC_PORT") else None
BITCOIN_RPC_USER = os.getenv("BITCOIN_RPC_USER")
BITCOIN_RPC_PASSWORD = os.getenv("BITCOIN_RPC_PASSWORD")
BITCOIN_CLI_PATH = os.getenv("BITCOIN_CLI_PATH")

LITECOIN_RPC_HOST = os.getenv("LITECOIN_RPC_HOST")
LITECOIN_RPC_PORT = int(os.getenv("LITECOIN_RPC_PORT", 9332))
LITECOIN_RPC_USER = os.getenv("LITECOIN_RPC_USER")
LITECOIN_RPC_PASSWORD = os.getenv("LITECOIN_RPC_PASSWORD")
LITECOIN_CLI_PATH = os.getenv("LITECOIN_CLI_PATH")

MAX_WORKERS = int(os.getenv("MAX_WORKERS", 100))
RPC_TIMEOUT = float(os.getenv("RPC_TIMEOUT", 5.0))
MAX_CONNECTIONS = int(os.getenv("MAX_CONNECTIONS", 100))
MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("MAX_KEEPALIVE_CONNECTIONS", 20))

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
USE_CHUNKS = bool(str_to_bool(os.getenv("USE_CHUNKS", "false")))
USE_RPC = bool(str_to_bool(os.getenv("USE_RPC", "false")))
STORE_BLOCKS = bool(str_to_bool(os.getenv("STORE_BLOCKS", "false")))

LITECOIN_BLOCKS_PATH = str(os.getenv("LITECOIN_BLOCKS_PATH"))
BITCOIN_BLOCKS_PATH = str(os.getenv("BITCOIN_BLOCKS_PATH"))

