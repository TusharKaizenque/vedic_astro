# services/retrieval/reranker.py — full replacement

import logging
import httpx
from models.knowledge import KnowledgeChunk, RerankedChunk
from config import settings

logger = logging.getLogger(__name__)

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"


async def rerank_chunks(
    query: str,
    chart_context: str,
    chunks: list[KnowledgeChunk],
    top_n: int | None = None,
) -> list[RerankedChunk]:
    if not chunks:
        return []

    top_n = top_n or settings.max_retrieval_chunks
    if not settings.jina_api_key:
        logger.warning("JINA_API_KEY is not configured; preserving retrieval order")
        return [
            RerankedChunk(chunk=c, relevance_score=0.5, retrieval_rank=i + 1)
            for i, c in enumerate(chunks[:top_n])
        ]

    enriched_query = f"{query}\n\nChart context: {chart_context[:300]}"
    documents = [chunk.content for chunk in chunks]

    payload = {
        "model": "jina-reranker-v2-base-multilingual",
        "query": enriched_query,
        "documents": documents,
        "top_n": min(top_n, len(chunks)),
    }

    headers = {
        "Authorization": f"Bearer {settings.jina_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                JINA_RERANK_URL,
                json=payload,
                headers=headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

        reranked: list[RerankedChunk] = []
        for i, result in enumerate(data.get("results", [])):
            original_chunk = chunks[result["index"]]
            reranked.append(RerankedChunk(
                chunk=original_chunk,
                relevance_score=float(result["relevance_score"]),
                retrieval_rank=i + 1,
            ))
        return reranked

    except Exception as e:
        logger.error(f"Jina rerank failed: {e}. Falling back to original order.")
        return [
            RerankedChunk(chunk=c, relevance_score=0.5, retrieval_rank=i + 1)
            for i, c in enumerate(chunks[:top_n])
        ]
