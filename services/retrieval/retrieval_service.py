import asyncio
import logging

from config import settings
from database.mongodb import knowledge_collection
from utils.embeddings_client import embed as _embed_text
from models.chart import NormalizedChart
from models.intent import IntentResult
from models.knowledge import KnowledgeChunk, RerankedChunk
from services.retrieval.query_builder import build_retrieval_queries
from services.retrieval.reranker import rerank_chunks
from services.rule_engine.engine import RuleEngineResult

logger = logging.getLogger(__name__)


async def _get_embedding(text: str) -> list[float]:
    return await _embed_text(text)


async def _vector_search(embedding: list[float], metadata_filter: dict, limit: int = 20) -> list[KnowledgeChunk]:
    if not embedding:
        return []
    stage = {
        "index": "knowledge_vector_index", "path": "embedding",
        "queryVector": embedding, "numCandidates": 100, "limit": limit,
    }
    if metadata_filter:
        stage["filter"] = metadata_filter
    pipeline = [
        {"$vectorSearch": stage},
        {"$project": {"_id": 0, "embedding": 0}},
    ]
    try:
        docs = await knowledge_collection().aggregate(pipeline).to_list(length=limit)
        return _validate(docs)
    except Exception as exc:
        logger.warning("Vector search unavailable (Atlas index required): %s", exc)
        return []


async def _text_search(text: str, limit: int = 10) -> list[KnowledgeChunk]:
    try:
        cursor = knowledge_collection().find(
            {"$text": {"$search": text}},
            {"_id": 0, "embedding": 0, "score": {"$meta": "textScore"}},
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        return _validate(await cursor.to_list(length=limit))
    except Exception as exc:
        # Missing text index or DB blip must not sink the whole query — degrade to [].
        logger.warning("Text search failed: %s", exc)
        return []


def _validate(documents: list[dict]) -> list[KnowledgeChunk]:
    chunks = []
    for document in documents:
        document.pop("score", None)
        try:
            chunks.append(KnowledgeChunk(**document))
        except Exception as exc:
            logger.warning("Skipping malformed knowledge chunk: %s", exc)
    return chunks


async def fetch_targeted_chunks(significators) -> list[KnowledgeChunk]:
    """Direct, exact-metadata fetch of the chunks the assembler needs for each factor.

    The semantic (text/vector) search is fuzzy and capped, so precise factor/yoga/dasha
    chunks get crowded out — they show up as false 'gaps' even when they exist. Because
    our reasoning is factor-driven and the assembler matches on exact metadata, we fetch
    those chunks directly (indexed lookups), guaranteeing grounding when content exists."""
    if significators is None:
        return []
    topic = significators.topic
    conditions: list[dict] = []
    for f in significators.factors:
        conditions.append({"chunk_type": "planet_in_house",
                           "planets_primary": f.planet, "houses_primary": f.placed_house})
        if f.sign:
            conditions.append({"chunk_type": "planet_in_sign",
                               "planets_primary": f.planet, "signs": f.sign})
        if f.lords_house:
            conditions.append({"chunk_type": "lord_in_house",
                               "houses_primary": {"$all": [f.lords_house, f.placed_house]}})
    if significators.relevant_yogas:
        conditions.append({"chunk_type": "yoga", "yoga_name": {"$in": significators.relevant_yogas}})
    if significators.primary_houses:
        conditions.append({"chunk_type": "house_signification",
                           "houses_primary": {"$in": significators.primary_houses},
                           "topics": topic})
    d = significators.dasha_activation
    if d and d.maha_lord:
        conditions.append({
            "chunk_type": {"$in": ["dasha_antardasha", "dasha_mahadasha", "dasha"]},
            "topics": topic,
            "$or": [{"dasha_pair": {"$all": [d.maha_lord, d.antar_lord]}},
                    {"planets_primary": d.maha_lord}],
        })
    if not conditions:
        return []
    try:
        docs = await knowledge_collection().find(
            {"$or": conditions}, {"_id": 0, "embedding": 0}
        ).to_list(length=120)
        return _validate(docs)
    except Exception:
        logger.exception("Targeted chunk fetch failed")
        return []


async def _search(query: dict) -> list[KnowledgeChunk]:
    text = query["text"]
    embedding, text_results = await asyncio.gather(_get_embedding(text), _text_search(text))
    vector_results = await _vector_search(embedding, query.get("metadata_filter", {}))
    combined = vector_results + text_results
    logger.debug("Query '%s': %d vector + %d text = %d unique", text[:60],
                 len(vector_results), len(text_results),
                 len({c.chunk_id for c in combined}))
    return list({chunk.chunk_id: chunk for chunk in combined}.values())


async def retrieve(
    intent: IntentResult,
    significators,   # SignificatorResult | None — avoid circular import
    chart: NormalizedChart | None,
    original_message: str,
    rule_result: RuleEngineResult | None = None,
) -> list[RerankedChunk]:
    queries = build_retrieval_queries(intent, chart, rule_result, original_message, significators)
    try:
        result_groups = await asyncio.gather(*(_search(query) for query in queries))
    except Exception:
        logger.exception("Hybrid retrieval failed")
        return []
    candidates = list({chunk.chunk_id: chunk for group in result_groups for chunk in group}.values())
    context = (
        f"Lagna {chart.lagna_sign}; Moon {chart.moon_sign}; "
        f"Dasha {chart.dasha.maha_dasha_lord}/{chart.dasha.antar_dasha_lord}"
        if chart else ""
    )
    reranked = await rerank_chunks(original_message, context, candidates)

    # Guarantee the exact factor/yoga/dasha chunks are present (not lost to the rerank cap).
    targeted = await fetch_targeted_chunks(significators)
    seen = {rc.chunk.chunk_id for rc in reranked}
    forced = [
        RerankedChunk(chunk=c, relevance_score=2.0, retrieval_rank=0)
        for c in targeted if c.chunk_id not in seen
    ]
    return forced + reranked
