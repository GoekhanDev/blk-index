import threading
from threading import Lock
import time
from typing import Dict, Any, Optional, List

from bitcoinrpc.authproxy import AuthServiceProxy

import config

class RPCClient:

    def __init__(self):
        self.rpc_clients = {}
        self.available_nodes = []
        self.nodes = self._init_all_rpc_clients()
        self.locks = {}
        self.local = threading.local()

    def _coin_config_available(self, coin: str) -> bool:
        """Check if RPC configuration is available for a given coin"""
        return all([
            getattr(config, f"{coin.upper()}_RPC_HOST", None),
            getattr(config, f"{coin.upper()}_RPC_PORT", None),
            getattr(config, f"{coin.upper()}_RPC_USER", None),
            getattr(config, f"{coin.upper()}_RPC_PASSWORD", None),
        ])

    def _get_rpc_url(self, coin: str) -> str:
        """Get RPC URL for a coin"""
        user = getattr(config, f"{coin.upper()}_RPC_USER")
        password = getattr(config, f"{coin.upper()}_RPC_PASSWORD")
        host = getattr(config, f"{coin.upper()}_RPC_HOST")
        port = getattr(config, f"{coin.upper()}_RPC_PORT")
        return f"http://{user}:{password}@{host}:{port}"

    def _get_thread_local_client(self, coin: str) -> AuthServiceProxy:
        """Get or create thread-local RPC client"""
        if not hasattr(self.local, 'clients'):
            self.local.clients = {}
        
        if coin not in self.local.clients:
            url = self._get_rpc_url(coin)
            self.local.clients[coin] = AuthServiceProxy(url, timeout=30)
        
        return self.local.clients[coin]

    def _init_all_rpc_clients(self) -> List[Dict[str, Any]]:
        """Initialize and verify RPC clients for supported coins and return results"""
        results = []
        for coin in ["bitcoin", "litecoin"]:
            if not self._coin_config_available(coin):
                
                results.append({
                    "coin": coin,
                    "success": False,
                    "error": f"{coin.capitalize()} config not available"
                })
                
                continue

            try:
                url = self._get_rpc_url(coin)
                client = AuthServiceProxy(url, timeout=30)
                client.getblockchaininfo()

                self.rpc_clients[coin] = url
                self.available_nodes.append(coin)
                self.locks[coin] = Lock()

                results.append({
                    "coin": coin,
                    "success": True,
                    "host": getattr(config, f"{coin.upper()}_RPC_HOST"),
                    "port": getattr(config, f"{coin.upper()}_RPC_PORT")
                })

            except Exception as e:
                results.append({
                    "coin": coin,
                    "success": False,
                    "error": str(e)
                })

        return results

    def rpc_auth(self, coin: str) -> tuple[str, str]:
        """Get credentials for a specific coin/node"""
        if coin not in self.available_nodes:
            raise ValueError(f"RPC node for '{coin}' is not available")
        user = getattr(config, f"{coin.upper()}_RPC_USER")
        password = getattr(config, f"{coin.upper()}_RPC_PASSWORD")
        return user, password

    async def rpc_call(self, coin: str, method: str, params: Optional[List[Any]] = None, max_retries: int = 3) -> Optional[Any]:
        """Make RPC call using thread-local client with retry logic"""
        if coin not in self.available_nodes:
            return {"error": f"RPC node for '{coin}' is not available"}

        for attempt in range(max_retries):
            try:

                client = self._get_thread_local_client(coin)
                result = getattr(client, method)(*(params or []))
                return result
                
            except Exception as e:
                error_str = str(e).lower()
                
                if "request-sent" in error_str or "connection" in error_str:
   
                    if hasattr(self.local, 'clients') and coin in self.local.clients:
                        del self.local.clients[coin]
                    
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                
                return {"error": str(e)}

        return {"error": f"Max retries ({max_retries}) exceeded"}

    async def get_blockchain_info(self, coin: str) -> Dict[str, Any]:
        """Get blockchain information including block count and prune status"""
        result = await self.rpc_call(coin, "getblockchaininfo")
        
        if isinstance(result, dict) and "error" in result:
            return result
        
        return {
            "blocks": result["blocks"],
            "pruneheight": result.get("pruneheight", 0) if result.get("pruned") else 0
        }
    
