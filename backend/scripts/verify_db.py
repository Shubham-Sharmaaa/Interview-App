"""
Run this once, by hand, after you've created your Atlas M0 cluster and
filled in MONGODB_URI in .env, and BEFORE building anything else on top
of the database layer.

    cd backend
    python -m scripts.verify_db

It inserts one throwaway document, reads it back, and deletes it. If this
doesn't print "DB VERIFIED OK", nothing later in the app will work either —
better to find that out now than after building three routes on top of it.
"""

import asyncio
from datetime import datetime, timezone

from app.db import get_client, close_client
from app.config import settings


async def main() -> None:
    client = get_client()
    db = client[settings.mongodb_db_name]
    collection = db["_verify_db_scratch"]

    probe = {"checked_at": datetime.now(timezone.utc), "purpose": "M0 verification"}

    print(f"Connecting to database '{settings.mongodb_db_name}'...")
    result = await collection.insert_one(probe)
    print(f"Inserted throwaway document: {result.inserted_id}")

    fetched = await collection.find_one({"_id": result.inserted_id})
    assert fetched is not None, "insert succeeded but the document couldn't be read back"
    print(f"Read it back: {fetched}")

    await collection.delete_one({"_id": result.inserted_id})
    print("Deleted the throwaway document.")

    await close_client()
    print("\nDB VERIFIED OK — AsyncMongoClient + your Atlas cluster are working together.")


if __name__ == "__main__":
    asyncio.run(main())
