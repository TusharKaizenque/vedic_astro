"""
Knowledge Base Ingestion Script
================================
Reads all JSON files from data/knowledge/, generates embeddings,
and upserts chunks into MongoDB's `knowledge` collection.

Usage (from vedic-astro-backend/ directory):
    python scripts/ingest_knowledge.py                  # ingest all files
    python scripts/ingest_knowledge.py --dry-run        # preview without writing
    python scripts/ingest_knowledge.py --file career_yogas.json  # single file

Prerequisites:
    1. MONGODB_URL set in .env (or environment)
    2. OPENAI_API_KEY (or EMBEDDING_API_KEY) set in .env for vector embeddings
    3. pip install motor openai python-dotenv (already in requirements.txt)

Atlas Vector Search Index setup (one-time, in Atlas UI):
    Collection: vedic_astro.knowledge
    Index name: knowledge_vector_index
    Index type: Vector Search
    Field: embedding
    Dimensions: 1536
    Similarity: cosine
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import motor.motor_asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Add parent directory to path so we can import config
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("ingest")

# ── Config ────────────────────────────────────────────────────────────────────
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB_NAME", "vedic_astro")
COLLECTION_NAME = "knowledge"

EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

DATA_DIR = Path(__file__).parent.parent / "data" / "knowledge"

BATCH_SIZE = 20  # embed N chunks at a time to stay within token limits


# ── Embedding client ──────────────────────────────────────────────────────────
def _make_embedding_client() -> AsyncOpenAI | None:
    if not EMBEDDING_API_KEY or EMBEDDING_API_KEY.startswith("test-"):
        logger.warning(
            "No EMBEDDING_API_KEY found. Chunks will be ingested WITHOUT embeddings "
            "(text search only — vector search will not work)."
        )
        return None
    kwargs: dict[str, Any] = {"api_key": EMBEDDING_API_KEY}
    if EMBEDDING_BASE_URL:
        kwargs["base_url"] = EMBEDDING_BASE_URL
    return AsyncOpenAI(**kwargs)


async def embed_batch(client: AsyncOpenAI | None, texts: list[str]) -> list[list[float]]:
    if client is None:
        return [[] for _ in texts]
    try:
        resp = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
    except Exception as exc:
        logger.error("Embedding batch failed: %s", exc)
        return [[] for _ in texts]


# ── File loading ──────────────────────────────────────────────────────────────
def load_chunks_from_file(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path.name}: expected a JSON array, got {type(data).__name__}")
    return data


def discover_files(single_file: str | None = None) -> list[Path]:
    if single_file:
        p = DATA_DIR / single_file
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        return [p]
    return sorted(DATA_DIR.glob("*.json"))


# ── MongoDB upsert ─────────────────────────────────────────────────────────────
async def upsert_chunks(collection, chunks: list[dict]) -> tuple[int, int]:
    inserted = updated = 0
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if not chunk_id:
            logger.warning("Chunk missing chunk_id — skipping: %s", str(chunk)[:80])
            continue
        result = await collection.replace_one(
            {"chunk_id": chunk_id},
            chunk,
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
        elif result.modified_count:
            updated += 1
    return inserted, updated


# ── Text index creation ────────────────────────────────────────────────────────
async def ensure_text_index(collection) -> None:
    existing = {name for name in await collection.index_information()}
    if any("text" in name.lower() or "content" in name.lower() for name in existing):
        return
    await collection.create_index(
        [
            ("content", "text"),
            ("topics", "text"),
            ("yoga_name", "text"),
        ],
        name="knowledge_text_index",
        default_language="english",
    )
    logger.info("Created text search index on knowledge collection")


# ── Main ingestion loop ────────────────────────────────────────────────────────
async def ingest(single_file: str | None = None, dry_run: bool = False) -> None:
    files = discover_files(single_file)
    if not files:
        logger.error("No JSON files found in %s", DATA_DIR)
        return

    logger.info("Found %d knowledge files in %s", len(files), DATA_DIR)

    # Load all chunks
    all_chunks: list[dict] = []
    for path in files:
        try:
            chunks = load_chunks_from_file(path)
            logger.info("  %s — %d chunks", path.name, len(chunks))
            all_chunks.extend(chunks)
        except Exception as exc:
            logger.error("  %s — FAILED to load: %s", path.name, exc)

    logger.info("Total chunks to process: %d", len(all_chunks))

    if dry_run:
        logger.info("[DRY RUN] Would embed and upsert %d chunks. Exiting.", len(all_chunks))
        for chunk in all_chunks:
            logger.info("  chunk_id=%s  type=%s  topics=%s",
                        chunk.get("chunk_id"), chunk.get("chunk_type"), chunk.get("topics"))
        return

    # Generate embeddings in batches
    emb_client = _make_embedding_client()
    texts = [chunk.get("content", "") for chunk in all_chunks]
    embeddings: list[list[float]] = []

    logger.info("Generating embeddings in batches of %d ...", BATCH_SIZE)
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        batch_embs = await embed_batch(emb_client, batch)
        embeddings.extend(batch_embs)
        logger.info("  Embedded %d/%d", min(i + BATCH_SIZE, len(texts)), len(texts))

    # Attach embeddings to chunks
    for chunk, emb in zip(all_chunks, embeddings):
        chunk["embedding"] = emb

    # Connect to MongoDB and upsert
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    await ensure_text_index(collection)

    logger.info("Upserting %d chunks into %s.%s ...", len(all_chunks), DB_NAME, COLLECTION_NAME)
    inserted, updated = await upsert_chunks(collection, all_chunks)

    client.close()

    embedded_count = sum(1 for e in embeddings if e)
    logger.info("")
    logger.info("=== Ingestion complete ===")
    logger.info("  Inserted (new):  %d", inserted)
    logger.info("  Updated (existing): %d", updated)
    logger.info("  With embeddings: %d / %d", embedded_count, len(all_chunks))
    if embedded_count < len(all_chunks):
        logger.warning(
            "  %d chunks have NO embedding (set EMBEDDING_API_KEY for vector search)",
            len(all_chunks) - embedded_count,
        )


def parse_args() -> tuple[str | None, bool]:
    import argparse
    parser = argparse.ArgumentParser(description="Ingest Vedic astrology knowledge base into MongoDB")
    parser.add_argument("--file", help="Ingest a single file from data/knowledge/ (e.g. career_yogas.json)")
    parser.add_argument("--dry-run", action="store_true", help="List chunks without writing to MongoDB")
    args = parser.parse_args()
    return args.file, args.dry_run


if __name__ == "__main__":
    file_arg, dry_run_arg = parse_args()
    asyncio.run(ingest(single_file=file_arg, dry_run=dry_run_arg))
