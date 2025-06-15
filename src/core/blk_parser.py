import struct
import hashlib
from io import BytesIO
import logger
import base58
from typing import Optional, Union, List, Dict, Any, BinaryIO


class parser:

    BIP34_COINBASE_ACTIVATION = {
        "bitcoin": 227_835,
        "litecoin": 32_000
    }

    def __init__(self, coin: str) -> None:
        """
        Initialize the parser with coin type.

        Args:
            coin (str): The cryptocurrency ('bitcoin' or 'litecoin').
        """
        self.coin = coin.lower()
        LTC_MAGIC_BYTES = b'\xfb\xc0\xb6\xdb'
        BTC_MAGIC_BYTES = b'\xf9\xbe\xb4\xd9'
        self.magic_bytes = LTC_MAGIC_BYTES if self.coin == "litecoin" else BTC_MAGIC_BYTES

    def read_block_sync(self, f: BinaryIO) -> Optional[bytes]:
        """
        Read a single raw block from a .dat file.

        Args:
            f (file): Binary file handle.

        Returns:
            bytes: Raw block data or None.
        """
        magic = f.read(4)
        if not magic:
            return None
        if magic != self.magic_bytes:
            raise ValueError(f"Invalid magic bytes: {magic.hex()}")
        size_bytes = f.read(4)
        if len(size_bytes) < 4:
            return None
        block_size = struct.unpack("<I", size_bytes)[0]
        block_data = f.read(block_size)
        if len(block_data) < block_size:
            raise ValueError("Incomplete block")
        return block_data

    def _extract_height_from_coinbase(self, coinbase_tx: Dict[str, Any]) -> Optional[int]:
        """
        Extract the block height from coinbase transaction via BIP-34.

        Args:
            coinbase_tx (dict): Parsed coinbase transaction.

        Returns:
            int: Block height or None if extraction fails.
        """
        try:
            script_hex = coinbase_tx['vin'][0]['scriptSig']
            if not script_hex:
                return None
            script = bytes.fromhex(script_hex)
            if len(script) == 0:
                return None
            push_len = script[0]
            if push_len < 1 or push_len > len(script) - 1 or push_len > 8:
                return None
            height_bytes = script[1:1 + push_len]
            return int.from_bytes(height_bytes, 'little')
        except Exception:
            return None

    def parse_block_sync(self, raw_bytes: bytes, height: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Parse a raw block into structured data.

        Args:
            raw_bytes (bytes): Raw block bytes.
            height (int, optional): Block height. Inferred from coinbase if None.

        Returns:
            dict: Parsed block.
        """
        try:
            f = BytesIO(raw_bytes)
            header_bytes = f.read(80)
            block_hash = hashlib.sha256(hashlib.sha256(header_bytes).digest())
            block_hash = block_hash.digest()[::-1].hex()
            f.seek(0)
            header = self.read_block_header_sync(f)
            tx_count = self.read_varint_sync(f)
            txs = []
            for _ in range(tx_count):
                try:
                    txs.append(self.parse_transaction_sync(f))
                except Exception as e:
                    if "unpack requires a buffer" not in str(e):
                        logger.debug(f"Transaction parse error: {e}")
                    break
            if height is None and txs:
                height = self._extract_height_from_coinbase(txs[0])
            return {
                "height": height,
                "hash": block_hash,
                "coin": self.coin,
                "timestamp": header.get("timestamp", 0),
                "tx_count": len(txs),
                "block": {
                    "header": header,
                    "tx": txs
                }
            }
        except Exception as e:
            if "unpack requires a buffer" not in str(e) or "Invalid magic bytes" not in str(e):
                logger.debug(f"Block parse error: {e}")
            return None

    def read_varint_sync(self, f: BinaryIO) -> Optional[int]:
        """
        Read a Bitcoin-style variable integer.

        Args:
            f (file): File-like object.

        Returns:
            int: Parsed varint.
        """
        i = f.read(1)
        if not i:
            return None
        i = i[0]
        if i < 0xfd:
            return i
        elif i == 0xfd:
            return struct.unpack('<H', f.read(2))[0]
        elif i == 0xfe:
            return struct.unpack('<I', f.read(4))[0]
        else:
            return struct.unpack('<Q', f.read(8))[0]

    def read_hash_sync(self, f: BinaryIO) -> str:
        """
        Read a hash (32 bytes, reversed).

        Args:
            f (file): File-like object.

        Returns:
            str: Hex string of hash.
        """
        return f.read(32)[::-1].hex()

    def read_block_header_sync(self, f: BinaryIO) -> Dict[str, Union[int, str]]:
        """
        Read and parse the block header.

        Args:
            f (file): File-like object.

        Returns:
            dict: Block header fields.
        """
        version = struct.unpack('<I', f.read(4))[0]
        prev_block = self.read_hash_sync(f)
        merkle_root = self.read_hash_sync(f)
        timestamp = struct.unpack('<I', f.read(4))[0]
        bits = struct.unpack('<I', f.read(4))[0]
        nonce = struct.unpack('<I', f.read(4))[0]
        return {
            'version': version,
            'previous_block_hash': prev_block,
            'merkle_root': merkle_root,
            'timestamp': timestamp,
            'bits': bits,
            'nonce': nonce
        }

    def decode_address(self, script_hex: str) -> Optional[str]:
        """
        Decode the scriptPubKey into a human-readable address.

        Args:
            script_hex (str): ScriptPubKey in hex.

        Returns:
            str: Decoded address or None.
        """
        if not script_hex:
            return None
        
        script_len = len(script_hex)
        
        if script_len == 50 and script_hex.startswith("76a914") and script_hex.endswith("88ac"):
            pubkey_hash = script_hex[6:-4]
            version = b'\x30' if self.coin == "litecoin" else b'\x00'
            return self._encode_address(version, pubkey_hash)
        
        elif script_len == 46 and script_hex.startswith("a914") and script_hex.endswith("87"):
            script_hash = script_hex[4:-2]
            version = b'\x32' if self.coin == "litecoin" else b'\x05'
            return self._encode_address(version, script_hash)
        
        elif script_hex.endswith("ac") and script_len in [68, 136]:
            pubkey_hex = script_hex[:-2]
            try:
                pubkey_bytes = bytes.fromhex(pubkey_hex)
                if len(pubkey_bytes) in [33, 65]:
                    pubkey_hash = hashlib.sha256(hashlib.new('ripemd160', hashlib.sha256(pubkey_bytes).digest()).digest()).digest()[:20]
                    version = b'\x30' if self.coin == "litecoin" else b'\x00'
                    return self._encode_address(version, pubkey_hash.hex())
            except Exception:
                pass
        
        elif script_len == 44 and script_hex.startswith("0014"):
            if self.coin == "bitcoin":
                pubkey_hash = script_hex[4:]
                return self._encode_bech32("bc", 0, bytes.fromhex(pubkey_hash))
            elif self.coin == "litecoin":
                pubkey_hash = script_hex[4:]  
                return self._encode_bech32("ltc", 0, bytes.fromhex(pubkey_hash))
        
        elif script_len == 68 and script_hex.startswith("0020"):
            if self.coin == "bitcoin":
                script_hash = script_hex[4:]
                return self._encode_bech32("bc", 0, bytes.fromhex(script_hash))
            elif self.coin == "litecoin":
                script_hash = script_hex[4:]
                return self._encode_bech32("ltc", 0, bytes.fromhex(script_hash))
        
        elif script_hex.startswith("6a"):
            return None
        
        return None

    def _encode_address(self, version: bytes, hash_hex: str) -> Optional[str]:
        """
        Encode address using Base58Check.

        Args:
            version (bytes): Version byte.
            hash_hex (str): Hash in hex format.

        Returns:
            str: Base58Check encoded address.
        """
        try:
            hash_bytes = bytes.fromhex(hash_hex)
            checksum_input = version + hash_bytes
            checksum = hashlib.sha256(hashlib.sha256(checksum_input).digest()).digest()[:4]
            return base58.b58encode(checksum_input + checksum).decode()
        except Exception:
            return None

    def _encode_bech32(self, hrp: str, witver: int, witprog: bytes) -> Optional[str]:
        """
        Encode Bech32 address (simplified implementation).

        Args:
            hrp (str): Human readable part.
            witver (int): Witness version.
            witprog (bytes): Witness program.

        Returns:
            str: Bech32 encoded address or None.
        """
        try:
            spec = self._bech32_polymod_step(self._bech32_hrp_expand(hrp) + [witver] + self._convertbits(witprog, 8, 5))
            if spec is None:
                return None
            return hrp + '1' + ''.join([self._bech32_charset[d] for d in [witver] + self._convertbits(witprog, 8, 5) + self._bech32_create_checksum(hrp, [witver] + self._convertbits(witprog, 8, 5))])
        except Exception:
            return None

    def _bech32_hrp_expand(self, hrp: str) -> List[int]:
        """Expand the HRP into values for checksum computation."""
        return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]

    def _bech32_polymod_step(self, values: List[int]) -> int:
        """Internal function for bech32 polymod."""
        GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
        chk = 1
        for value in values:
            top = chk >> 25
            chk = (chk & 0x1ffffff) << 5 ^ value
            for i in range(5):
                chk ^= GEN[i] if ((top >> i) & 1) else 0
        return chk

    def _bech32_create_checksum(self, hrp: str, data: List[int]) -> List[int]:
        """Compute the checksum values given HRP and data."""
        values = self._bech32_hrp_expand(hrp) + data
        polymod = self._bech32_polymod_step(values + [0, 0, 0, 0, 0, 0]) ^ 1
        return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]

    def _convertbits(self, data: Union[bytes, List[int]], frombits: int, tobits: int, pad: bool = True) -> Optional[List[int]]:
        """General power-of-2 base conversion."""
        acc = 0
        bits = 0
        ret = []
        maxv = (1 << tobits) - 1
        max_acc = (1 << (frombits + tobits - 1)) - 1
        for value in data:
            if value < 0 or (value >> frombits):
                return None
            acc = ((acc << frombits) | value) & max_acc
            bits += frombits
            while bits >= tobits:
                bits -= tobits
                ret.append((acc >> bits) & maxv)
        if pad:
            if bits:
                ret.append((acc << (tobits - bits)) & maxv)
        elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
            return None
        return ret

    _bech32_charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

    def parse_transaction_sync(self, f: BinaryIO) -> Dict[str, Any]:
        """
        Parse a Bitcoin-style transaction from stream.

        Args:
            f (file): File-like object.

        Returns:
            dict: Parsed transaction.
        """
        start = f.tell()
        tx = {}
        tx['version'] = struct.unpack('<I', f.read(4))[0]
        
        marker = f.read(1)
        if marker == b'\x00':
            flag = f.read(1)
            if flag == b'\x01':
                segwit = True
            else:
                segwit = False
                f.seek(-2, 1)
        else:
            segwit = False
            f.seek(-1, 1)
        
        vin_count = self.read_varint_sync(f)
        tx['vin'] = []
        for _ in range(vin_count):
            vin = {
                'txid': self.read_hash_sync(f),
                'vout': struct.unpack('<I', f.read(4))[0]
            }
            script_len = self.read_varint_sync(f)
            vin['scriptSig'] = f.read(script_len).hex()
            vin['sequence'] = struct.unpack('<I', f.read(4))[0]
            tx['vin'].append(vin)
        
        vout_count = self.read_varint_sync(f)
        tx['vout'] = []
        for i in range(vout_count):
            vout = {
                'value': struct.unpack('<Q', f.read(8))[0] / 1e8
            }
            script_len = self.read_varint_sync(f)
            script_hex = f.read(script_len).hex()
            vout['scriptPubKey'] = script_hex
            vout['address'] = self.decode_address(script_hex)
            vout['n'] = i
            tx['vout'].append(vout)
        
        if segwit:
            for vin in tx['vin']:
                n_items = self.read_varint_sync(f)
                vin['witness'] = []
                for _ in range(n_items):
                    item_len = self.read_varint_sync(f)
                    vin['witness'].append(f.read(item_len).hex())
        
        tx['locktime'] = struct.unpack('<I', f.read(4))[0]
        
        end = f.tell()
        f.seek(start)
        
        if segwit:
            temp_f = BytesIO()
            temp_f.write(struct.pack('<I', tx['version']))
            temp_f.write(struct.pack('<B', len(tx['vin'])) if len(tx['vin']) < 0xfd else self._write_varint(len(tx['vin'])))
            
            for vin in tx['vin']:
                temp_f.write(bytes.fromhex(vin['txid'])[::-1])
                temp_f.write(struct.pack('<I', vin['vout']))
                script_bytes = bytes.fromhex(vin['scriptSig'])
                if len(script_bytes) < 0xfd:
                    temp_f.write(struct.pack('<B', len(script_bytes)))
                else:
                    temp_f.write(self._write_varint(len(script_bytes)))
                temp_f.write(script_bytes)
                temp_f.write(struct.pack('<I', vin['sequence']))
            
            if len(tx['vout']) < 0xfd:
                temp_f.write(struct.pack('<B', len(tx['vout'])))
            else:
                temp_f.write(self._write_varint(len(tx['vout'])))
                
            for vout in tx['vout']:
                temp_f.write(struct.pack('<Q', int(vout['value'] * 1e8)))
                script_bytes = bytes.fromhex(vout['scriptPubKey'])
                if len(script_bytes) < 0xfd:
                    temp_f.write(struct.pack('<B', len(script_bytes)))
                else:
                    temp_f.write(self._write_varint(len(script_bytes)))
                temp_f.write(script_bytes)
                
            temp_f.write(struct.pack('<I', tx['locktime']))
            raw_tx = temp_f.getvalue()
        else:
            raw_tx = f.read(end - start)
        
        tx['txid'] = hashlib.sha256(hashlib.sha256(raw_tx).digest()).digest()[::-1].hex()
        return tx

    def _write_varint(self, n: int) -> bytes:
        """
        Write a variable integer to bytes.

        Args:
            n (int): Integer to encode.

        Returns:
            bytes: Encoded varint.
        """
        if n < 0xfd:
            return struct.pack('<B', n)
        elif n <= 0xffff:
            return struct.pack('<BH', 0xfd, n)
        elif n <= 0xffffffff:
            return struct.pack('<BI', 0xfe, n)
        else:
            return struct.pack('<BQ', 0xff, n)
        
    def _extract_address_from_scriptsig(self, scriptsig_hex: str) -> Optional[str]:
        """
        Extract address from scriptSig (limited capability for pruned nodes).

        Args:
            scriptsig_hex (str): ScriptSig in hex format.

        Returns:
            str: Extracted address or None.
        """
        if not scriptsig_hex:
            return None
            
        try:
            script_bytes = bytes.fromhex(scriptsig_hex)

            if len(script_bytes) < 33:
                return None

            i = 0
            while i < len(script_bytes):
                if script_bytes[i] == 0x30 and i + 1 < len(script_bytes):
                    sig_len = script_bytes[i + 1]
                    if sig_len > 0 and i + 2 + sig_len < len(script_bytes):
                  
                        pubkey_start = i + 2 + sig_len + 1
                        if pubkey_start < len(script_bytes):
                            pubkey_len = script_bytes[pubkey_start - 1]
                            if pubkey_len in [33, 65] and pubkey_start + pubkey_len <= len(script_bytes):
                                pubkey = script_bytes[pubkey_start:pubkey_start + pubkey_len]
                                
                                pubkey_hash = hashlib.new('ripemd160', hashlib.sha256(pubkey).digest()).digest()
                                version = b'\x30' if self.coin == "litecoin" else b'\x00'
                                checksum_input = version + pubkey_hash
                                checksum = hashlib.sha256(hashlib.sha256(checksum_input).digest()).digest()[:4]
                                return base58.b58encode(checksum_input + checksum).decode()
                        break
                i += 1
            
            return None
            
        except Exception:
            return None

    async def read_block(self, f: BinaryIO) -> Optional[bytes]:
        return self.read_block_sync(f)

    async def read_varint(self, f: BinaryIO) -> Optional[int]:
        return self.read_varint_sync(f)

    async def read_hash(self, f: BinaryIO) -> str:
        return self.read_hash_sync(f)

    async def read_block_header(self, f: BinaryIO) -> Dict[str, Union[int, str]]:
        return self.read_block_header_sync(f)

    async def parse_transaction(self, f: BinaryIO) -> Dict[str, Any]:
        return self.parse_transaction_sync(f)

    async def parse_block(self, raw_bytes: bytes, height: Optional[int] = None) -> Optional[Dict[str, Any]]:
        return self.parse_block_sync(raw_bytes, height)
