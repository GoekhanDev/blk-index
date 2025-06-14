import asyncio
from core.indexer import index

async def main():
    indexer = index("litecoin")
    await indexer.run()

if __name__ == "__main__":
    asyncio.run(main())