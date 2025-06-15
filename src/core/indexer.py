import asyncio, threading, glob, os, gc, hashlib, base58
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List, Tuple

from logger import logger
from database import get_storage
from config import (
    USE_CHUNKS,
    CHUNK_SIZE,
    MAX_WORKERS,
    STORE_BLOCKS,
    LITECOIN_BLOCKS_PATH,
    BITCOIN_BLOCKS_PATH,
    USE_RPC
)

from utils.progressbar import progress_bar
from core.node.rpc import RPCClient
from core.node.cli import CLIClient
from core.blk_parser import parser

class index:

    def __init__(self, coin: str):
        """
        Initialize the indexer with the specified coin.

        Args:
            coin (str): The cryptocurrency ('bitcoin' or 'litecoin').
        """
        self.fetched_blocks = 0
        self.coin = coin

        self.database = get_storage(self.coin)
        self.stop_event = threading.Event()
        self.lock = Lock()

        self.rpc = RPCClient()
        self.cli = CLIClient()
        self.node = self.rpc if USE_RPC else self.cli
        self.parser = parser(self.coin)

        self.use_chunks = USE_CHUNKS
        self.insert_chunk_size = CHUNK_SIZE
        self.max_workers = MAX_WORKERS
        self.store_blocks = STORE_BLOCKS

        self.block_path = LITECOIN_BLOCKS_PATH if self.coin == "litecoin" else BITCOIN_BLOCKS_PATH

    async def run(self) -> None:
        """
        Run the indexing process.
        """
        blocks_to_index, start_height, end_height = await self.get_blocks()

        logger.info(f"{self.coin.upper()}: Parsing block files...")
        block_paths = await self.parse_blk_files()

        await self.index_blocks(blocks_to_index, block_paths)
        await self.verify_indexed_blocks(start_height, end_height)

    async def get_blocks(self) -> Tuple[int, int, int]:
        """
        Get the range of blocks to be indexed.

        Returns:
            Tuple[int, int, int]: Number of blocks to index, start height, end height.
        """
        info = await self.node.get_blockchain_info(self.coin)
        start_height = info["blocks"]
        end_height = info["pruneheight"]

        blocks_to_index = len(range(start_height, end_height - 1, -1))
        logger.info(f"{self.coin.upper()}: {blocks_to_index} Blocks Detected")

        return blocks_to_index, start_height, end_height

    async def parse_blk_files(self) -> List[str]:
        """
        Get the list of block file paths.

        Returns:
            List[str]: List of block file paths.
        """
        return sorted(glob.glob(f'{self.block_path}blk*'))

    async def index_blocks(self, blocks_to_index: int, block_paths: List[str]) -> None:
        """
        Index blocks from the given file paths.

        Args:
            blocks_to_index (int): Number of blocks expected to be indexed.
            block_paths (List[str]): List of paths to block files.
        """
        logger.info(f"{self.coin.upper()}: Starting indexing of {self.coin} blocks...")

        self.stop_event.clear()
        fetched_blocks_ref = [0]

        progress_thread = threading.Thread(
            target=progress_bar,
            args=(blocks_to_index, "Indexing blocks", self.stop_event, self.lock, fetched_blocks_ref),
            daemon=True
        )
        progress_thread.start()

        def parse_block_file(file_path: str) -> int:
            """
            Parse and index a single block file.

            Args:
                file_path (str): Path to the block file.

            Returns:
                int: Number of blocks processed.
            """
            blocks = []
            processed_count = 0

            try:
                with open(file_path, 'rb') as f:
                    while True:
                        try:
                            block_data = self.parser.read_block_sync(f)
                            if block_data is None:
                                break

                            block = self.parser.parse_block_sync(block_data)
                            if block:
                                if self.use_chunks:
                                    blocks.append(block)
                                    if len(blocks) >= self.insert_chunk_size:
                                        if self.store_blocks:
                                            asyncio.run(self.database.store_blocks_batch(blocks))
                                        self.process_and_store_transactions_batch(blocks)
                                        blocks.clear()
                                        gc.collect()
                                else:
                                    if self.store_blocks:
                                        asyncio.run(self.database.store_block(block))
                                    self.process_and_store_transactions(block)
                                    del block

                                processed_count += 1
                                with self.lock:
                                    fetched_blocks_ref[0] += 1

                        except Exception as e:
                            if "unpack requires a buffer" not in str(e) or "Invalid magic bytes" not in str(e):
                                logger.debug(f"Block parse error: {e}")
                            break

            except Exception as e:
                logger.error(f"Error opening file {file_path}: {e}")
                return processed_count

            if self.use_chunks and blocks:
                try:
                    if self.store_blocks:
                        asyncio.run(self.database.store_blocks_batch(blocks))
                    self.process_and_store_transactions_batch(blocks)
                    blocks.clear()
                    del blocks
                    gc.collect()
                except Exception as e:
                    logger.error(f"Error storing final batch from {os.path.basename(file_path)}: {e}")

            return processed_count

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(parse_block_file, file_path): file_path 
                    for file_path in block_paths
                }

                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        processed_count = future.result()
                    except Exception as e:
                        logger.error(f"Error processing {os.path.basename(file_path)}: {e}")
                    finally:
                        del future_to_file[future]

        finally:
            self.stop_event.set()
            if progress_thread.is_alive():
                progress_thread.join(timeout=2)

        logger.info(f"{self.coin.upper()}: Indexing completed! Processed {fetched_blocks_ref[0]} blocks")

    async def store_blocks_batch(self, blocks: List[Dict[str, Any]]) -> None:
        """
        Store a batch of parsed block data.

        Args:
            blocks (List[Dict[str, Any]]): List of block dictionaries.
        """
        try:
            for block in blocks:
                await self.database.store_block(block)
        except Exception as e:
            logger.error(f"Error storing blocks: {e}")

    async def verify_indexed_blocks(self, start_height: int, end_height: int) -> None:
        """
        Verify that all blocks in the range have been indexed.

        Args:
            start_height (int): Start height of the block range.
            end_height (int): End height of the block range.
        """
        if not self.store_blocks:
            logger.info(f"{self.coin.upper()}: Block storage disabled, skipping block verification.")
            return
            
        expected = set(range(end_height, start_height + 1))
        actual = set(await self.database.get_indexed_block_heights(end_height, start_height))
        missing = expected - actual

        if missing:
            logger.error(f"{self.coin.upper()}: Missing {len(missing)} Blocks")
        else:
            logger.info(f"{self.coin.upper()}: All blocks from height {end_height} to {start_height} are indexed.")

    def process_and_store_transactions_batch(self, blocks: List[Dict[str, Any]]) -> None:
        """
        Process and store transactions for a batch of blocks efficiently.

        Args:
            blocks (List[Dict[str, Any]]): List of parsed block data.
        """
        all_tx_docs = []
        
        for block in blocks:
            block_hash = block.get("hash")
            block_height = block.get("height")
            block_time = block.get("timestamp")

            txs = block.get("block", {}).get("tx", [])
            
            for tx in txs:
                txid = tx.get("txid")
                
                vin = []
                for v in tx.get("vin", []):
                    vin_txid = v.get("txid")
                    vin_vout = v.get("vout")
                    
                    if vin_txid == "0000000000000000000000000000000000000000000000000000000000000000" and vin_vout == 4294967295:
                        vin.append({
                            "txid": vin_txid,
                            "vout": vin_vout,
                            "address": "coinbase",
                            "value": 0,
                        })
                    else:
                        address = self.parser._extract_address_from_scriptsig(v.get("scriptSig", ""))
                        vin.append({
                            "txid": vin_txid,
                            "vout": vin_vout,
                            "address": address,
                            "value": 0,
                        })

                vout = []
                for out in tx.get("vout", []):
                    address = out.get("address")
                    if address is None and out.get("scriptPubKey"):
                        address = self.parser.decode_address(out.get("scriptPubKey"))
                    
                    vout.append({
                        "n": out.get("n", 0),
                        "address": address,
                        "value": out.get("value", 0),
                    })

                all_tx_docs.append({
                    "txid": txid,
                    "blockHash": block_hash,
                    "blockHeight": block_height,
                    "timestamp": block_time,
                    "vin": vin,
                    "vout": vout,
                })

        if all_tx_docs:
            try:
                self.database.transactions_collection.insert_many(all_tx_docs, ordered=False)
            except Exception as e:
                logger.warning(f"Failed to insert transaction batch: {e}")

    def process_and_store_transactions(self, block: Dict[str, Any]) -> None:
        """
        Process and store transactions for a given block.

        Args:
            block (Dict[str, Any]): Parsed block data.
        """
        block_hash = block.get("hash")
        block_height = block.get("height")
        block_time = block.get("timestamp")

        txs = block.get("block", {}).get("tx", [])
        tx_docs = []

        for tx in txs:
            txid = tx.get("txid")
            
            vin = []
            for v in tx.get("vin", []):
                vin_txid = v.get("txid")
                vin_vout = v.get("vout")
                
                if vin_txid == "0000000000000000000000000000000000000000000000000000000000000000" and vin_vout == 4294967295:
                    vin.append({
                        "txid": vin_txid,
                        "vout": vin_vout,
                        "address": "coinbase",
                        "value": 0,
                    })
                else:
                    address = self._extract_address_from_scriptsig(v.get("scriptSig", ""))
                    vin.append({
                        "txid": vin_txid,
                        "vout": vin_vout,
                        "address": address,
                        "value": 0,
                    })

            vout = []
            for out in tx.get("vout", []):
                address = out.get("address")
                if address is None and out.get("scriptPubKey"):
                    address = self.parser.decode_address(out.get("scriptPubKey"))
                
                vout.append({
                    "n": out.get("n", 0),
                    "address": address,
                    "value": out.get("value", 0),
                })

            tx_docs.append({
                "txid": txid,
                "blockHash": block_hash,
                "blockHeight": block_height,
                "timestamp": block_time,
                "vin": vin,
                "vout": vout,
            })

        if tx_docs:
            try:
                self.database.transactions_collection.insert_many(tx_docs, ordered=False)
            except Exception as e:
                logger.warning(f"Failed to insert TXs for block {block_height}: {e}")

