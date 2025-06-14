# 🚧 In Development

> This project is actively being developed. Expect changes and incomplete functionality.

---

# 🧱 Bitcoin/Litecoin Blockchain Indexer (for Pruned or Full Nodes)

This project provides a memory-efficient, modular indexer for parsing Bitcoin and Litecoin blockchains. It's designed primarily for **pruned nodes**, where full historical chain data is unavailable, but it also works seamlessly with **full nodes**.

The indexer reads raw `.blk` files directly from a node's data directory. It can also integrate with the node's RPC interface to determine blockchain metadata such as current height or prune height. Parsed data includes block headers, transactions (both inputs and outputs), and human-readable addresses derived from scripts using both legacy (Base58) and SegWit (Bech32) formats.

The entire system is built to be memory-efficient. It supports chunked parsing and storage, allowing it to index large datasets with limited memory. Threading and asynchronous operations are used to maximize throughput, and garbage collection is triggered where needed to keep memory use under control.

---

## ▶️ How to Use

Ensure your configuration is correctly set in `config.py` (e.g., block paths, whether to use RPC, and chunking preferences), then run:

```bash
python main.py
```

This will begin indexing the blockchain blocks from your local node's data directory.

## 📚 How It Works

### Block and Transaction Parsing

The `blk_parser.py` module handles raw parsing of blocks and transactions. It reads the Bitcoin/Litecoin binary block format directly, extracts headers, decodes all transaction inputs (`vin`) and outputs (`vout`), and attempts to derive the corresponding addresses. It supports various script formats including:

- Legacy P2PKH / P2SH
- SegWit P2WPKH / P2WSH
- Basic detection of OP_RETURN or unknown scripts

Bech32 and Base58 address formats are supported, depending on the coin and script type.

### Indexing Logic

The `indexer.py` module manages the high-level indexing process. It first collects all available `.blk` files, then uses a thread pool to process them concurrently. Each block is parsed and then inserted into the database — either one-by-one or in chunks based on your configuration.

Transaction data is also extracted and stored, including:

- Transaction ID
- All inputs and outputs
- Associated addresses
- Block hash, height, and timestamp

For pruned blocks, where inputs may not be fully available, the system makes a best-effort guess to recover addresses from `scriptSig` fields using public key extraction and hash reconstruction.

Progress is displayed in real time using a simple terminal progress bar utility.

---

## 🧪 Output Example

Each parsed block is stored as a structured dictionary. Example format:

```json
{
  "height": 123456,
  "hash": "000000000000...",
  "coin": "bitcoin",
  "timestamp": 1610000000,
  "tx_count": 123,
  "block": {
    "header": {
      "version": 536870912,
      "previous_block_hash": "...",
      "merkle_root": "...",
      "timestamp": 1610000000,
      "bits": 386803662,
      "nonce": 2083236893
    },
    "tx": [
      {
        "txid": "...",
        "vin": [...],
        "vout": [...]
      }
    ]
  }
}
```

---

## 🛠 Requirements

- Python 3.8+
- Install dependencies:

```bash
pip install -r requirements.txt
```


## 📜 License

This project is licensed under the **MIT License**.  
See the [LICENSE](LICENSE) file for full details.
