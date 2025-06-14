import asyncio
import json
import logger
import os

class CLIClient:
    def __init__(self):
        ...
    
    def get_cli_path(self, coin):
        default_paths = {
            "litecoin": "/home/litecoin/litecoin-node/litecoin-0.21.4/bin/litecoin-cli",
            "bitcoin": "/home/bitcoin/bitcoin-node/bitcoin-0.21.4/bin/bitcoin-cli"
        }

        return default_paths[coin]

    async def _run_cli(self, coin, *args, parse_json=True):
        try:
            process = await asyncio.create_subprocess_exec(
                self.get_cli_path(coin), *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_message = stderr.decode().strip()
                logger.error(f"error: {error_message}")
                raise RuntimeError(error_message)

            output = stdout.decode().strip()
            return json.loads(output) if parse_json else output

        except Exception as e:
            logger.error(f"exception: {str(e)}")
            raise

    async def get_blockchain_info(self, coin: str):
        return await self._run_cli(coin, "getblockchaininfo")

    async def get_block_hash(self, coin: str, height: int) -> str:
        return await self._run_cli(coin, "getblockhash", str(height), parse_json=False, )

    async def get_block(self, coin: str, block_hash: str) -> dict:
        return await self._run_cli(coin, "getblock", block_hash, "2")