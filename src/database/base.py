from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict

class DatabaseInterface(ABC):

    @abstractmethod
    async def store_blocks(self, block_data: List[Dict] = None) -> None:
        """Store block data."""
        ...

    @abstractmethod
    async def store_block(self, block_data: Dict = None) -> None:
        """Store block data."""
        ...
        
    @abstractmethod
    async def get_indexed_block_heights(self, start: int, end: int) -> List[int]:
        """Get list of block heights stored in DB between start and end (inclusive)."""
        ...

    @abstractmethod
    async def stream_blocks(self, batch_size: int = 100):
        """Stream blocks from the database."""
        ...
        
    @abstractmethod
    def get_transaction(self, txid: str) -> Dict[str, Any]:
        """Get transaction data."""
        ...