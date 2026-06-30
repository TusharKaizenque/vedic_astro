"""
Show the knowledge-base gaps — what classical content to author next, ranked by how often
users actually hit it.

Usage (from vedic-astro-backend/):
    python scripts/show_gaps.py
    python scripts/show_gaps.py --type factor      # only factor gaps
    python scripts/show_gaps.py --limit 50
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

import motor.motor_asyncio
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URI", os.getenv("MONGODB_URL", "mongodb://localhost:27017"))
DB_NAME = os.getenv("MONGODB_DB_NAME", "astro")


async def main(type_filter: str | None, limit: int) -> None:
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
    coll = client[DB_NAME]["knowledge_gaps"]
    query = {"type": type_filter} if type_filter else {}
    total = await coll.count_documents(query)
    if total == 0:
        print("No gaps logged yet. Ask some chart questions first, then re-run.")
        client.close()
        return

    cursor = coll.find(query).sort("count", -1).limit(limit)
    rows = await cursor.to_list(length=limit)

    by_type: dict[str, list] = {}
    for r in rows:
        by_type.setdefault(r.get("type", "?"), []).append(r)

    print(f"\n=== Knowledge-base gaps ({total} distinct, showing top {len(rows)}) ===")
    print("Author chunks for the highest-count items first.\n")
    for gtype in ("factor", "dasha", "yoga"):
        items = by_type.get(gtype, [])
        if not items:
            continue
        print(f"-- {gtype.upper()} ({len(items)}) --")
        for r in items:
            print(f"  [{r.get('count', 0):>3}x] {r.get('description', r.get('_id'))}")
        print()
    client.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=["factor", "dasha", "yoga"], help="filter by gap type")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()
    asyncio.run(main(args.type, args.limit))
