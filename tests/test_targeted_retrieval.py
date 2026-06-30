"""Test the targeted exact-metadata chunk fetch builds correct queries."""
from unittest.mock import patch

import pytest

from services.retrieval import retrieval_service
from services.significator_engine import (
    DashaActivation, SignificatorFactor, SignificatorResult,
)


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length):
        return self._docs


class _FakeColl:
    def __init__(self):
        self.last_query = None

    def find(self, query, projection=None):
        self.last_query = query
        return _FakeCursor([])


def _sig():
    f1 = SignificatorFactor(role="10th lord", planet="Saturn", placed_house=2, sign="Taurus",
                            dignity="friendly sign", functional_nature="malefic", dig_bala=False,
                            aspects_topic_house=False, kind="neutral", lords_house=10)
    f2 = SignificatorFactor(role="karaka", planet="Sun", placed_house=4, sign="Cancer",
                            dignity="friendly sign", functional_nature="benefic", dig_bala=False,
                            aspects_topic_house=False, kind="supporting")
    return SignificatorResult(
        topic="career", primary_houses=[10, 6, 2, 11], karaka_planets=["Sun"],
        relevant_varga="D10", factors=[f1, f2],
        dasha_activation=DashaActivation(maha_lord="Ketu", antar_lord="Venus", maha_end="",
                                         antar_end="", maha_is_significator=False,
                                         antar_is_significator=False,
                                         maha_functional_nature="neutral",
                                         antar_functional_nature="benefic",
                                         activation_strength="weak"),
        relevant_yogas=["Raja Yoga"], relevant_doshas=[],
        planets_in_topic_houses={}, aspects_on_topic_houses={},
    )


@pytest.mark.asyncio
async def test_targeted_fetch_builds_factor_yoga_dasha_conditions():
    fake = _FakeColl()
    with patch("services.retrieval.retrieval_service.knowledge_collection", return_value=fake):
        await retrieval_service.fetch_targeted_chunks(_sig())

    conditions = fake.last_query["$or"]
    # planet_in_house for Saturn in 2
    assert {"chunk_type": "planet_in_house", "planets_primary": "Saturn", "houses_primary": 2} in conditions
    # planet_in_sign for Sun in Cancer
    assert {"chunk_type": "planet_in_sign", "planets_primary": "Sun", "signs": "Cancer"} in conditions
    # lord_in_house for the 10th lord placed in the 2nd
    assert {"chunk_type": "lord_in_house", "houses_primary": {"$all": [10, 2]}} in conditions
    # yoga condition
    assert any(c.get("chunk_type") == "yoga" and c.get("yoga_name", {}).get("$in") == ["Raja Yoga"]
               for c in conditions)
    # dasha condition references the maha lord and topic
    assert any(c.get("topics") == "career" and "$or" in c and
               c.get("chunk_type", {}).get("$in") for c in conditions)


@pytest.mark.asyncio
async def test_targeted_fetch_none_significators():
    assert await retrieval_service.fetch_targeted_chunks(None) == []
