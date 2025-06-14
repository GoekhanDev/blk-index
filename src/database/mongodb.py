from pymongo import MongoClient
from typing import Any, Dict, List
from database.base import DatabaseInterface
from logger import logger

class MongoDatabase(DatabaseInterface):
    
    def __init__(self, uri: str, db_name: str):
        """
        Initialize MongoDB database connection.

        Args:
            uri (str): MongoDB connection URI.
            db_name (str): Database name.
        """
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.blocks_collection = self.db["blocks"]
        self.transactions_collection = self.db["transactions"]

    async def store_blocks(self, block_data: List[Dict[str, Any]]) -> None:
        """
        Store multiple blocks in the database.

        Args:
            block_data (List[Dict[str, Any]]): List of block dictionaries to store.
        """
        try:
            self.blocks_collection.insert_many(block_data, ordered=False)
        except Exception as e:
            logger.error(f"Error inserting blocks: {e}")
            raise

    async def store_blocks_batch(self, block_data: List[Dict[str, Any]]) -> None:
        """
        Store a batch of blocks efficiently.

        Args:
            block_data (List[Dict[str, Any]]): List of block dictionaries to store.
        """
        try:
            if block_data:
                self.blocks_collection.insert_many(block_data, ordered=False)
        except Exception as e:
            logger.error(f"Error inserting block batch: {e}")
            raise

    async def store_block(self, block_data: Dict[str, Any]) -> None:
        """
        Store a single block in the database.

        Args:
            block_data (Dict[str, Any]): Block dictionary to store.
        """
        try:
            self.blocks_collection.insert_one(block_data)
        except Exception as e:
            logger.error(f"Error inserting block at height {block_data.get('height')}: {e}")
            raise

    async def get_indexed_block_heights(self, start: int, end: int) -> List[int]:
        """
        Get list of indexed block heights within a range.

        Args:
            start (int): Start height (inclusive).
            end (int): End height (inclusive).

        Returns:
            List[int]: List of indexed block heights.
        """
        try:
            cursor = self.blocks_collection.find(
                {"height": {"$gte": start, "$lte": end}},
                {"_id": 0, "height": 1}
            )
            return [doc["height"] for doc in cursor if doc.get("height") is not None]
        except Exception as e:
            logger.error(f"Error fetching indexed block heights: {e}")
            return []
        
    async def stream_blocks(self, batch_size: int = 100):
        """
        Stream blocks from the database in batches.

        Args:
            batch_size (int): Number of blocks per batch.

        Yields:
            Dict[str, Any]: Individual block data.
        """
        try:
            cursor = self.blocks_collection.find({}, {"_id": 0}).batch_size(batch_size)
            for block in cursor:
                yield block
        except Exception as e:
            logger.error(f"Error streaming blocks: {e}")
            return
        
    def get_transaction(self, txid: str) -> Dict[str, Any]:
        """
        Get a transaction by its ID.

        Args:
            txid (str): Transaction ID.

        Returns:
            Dict[str, Any]: Transaction data or None if not found.
        """
        try:
            return self.transactions_collection.find_one({"txid": txid}, {"_id": 0})
        except Exception as e:
            logger.error(f"Error fetching transaction {txid}: {e}")
            return None

    def store_transactions_batch(self, tx_data: List[Dict[str, Any]]) -> None:
        """
        Store a batch of transactions efficiently.

        Args:
            tx_data (List[Dict[str, Any]]): List of transaction dictionaries.
        """
        try:
            if tx_data:
                self.transactions_collection.insert_many(tx_data, ordered=False)
        except Exception as e:
            logger.error(f"Error inserting transaction batch: {e}")
            raise