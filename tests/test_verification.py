"""Tests for the Phase-3 verification pass (review_reading): pass-through, refine, and degrade."""
import types

import pytest

import services.verification_service as vs


class _FakeMessage:
    def __init__(self, content): self.message = types.SimpleNamespace(content=content)


class _FakeResp:
    def __init__(self, content): self.choices = [_FakeMessage(content)]


def _client_returning(content):
    async def _create(**kwargs): return _FakeResp(content)
    return types.SimpleNamespace(chat=types.SimpleNamespace(
        completions=types.SimpleNamespace(create=_create)))


def _client_raising():
    async def _create(**kwargs): raise RuntimeError("boom")
    return types.SimpleNamespace(chat=types.SimpleNamespace(
        completions=types.SimpleNamespace(create=_create)))


DRAFT = "**In plain language**\nYour career is grounded and rising.\n\n**The astrology behind this**\nThe 10th lord is strong."


@pytest.mark.asyncio
async def test_short_draft_passthrough_no_llm():
    # Too short to be worth reviewing → returned unchanged, no LLM call.
    res = await vs.review_reading("hi", "blocks", "q")
    assert res.ok and not res.refined and res.text == "hi"


@pytest.mark.asyncio
async def test_clean_draft_passthrough(monkeypatch):
    monkeypatch.setattr(vs, "get_llm_client", lambda: _client_returning("PASS"))
    res = await vs.review_reading(DRAFT, "BLOCKS", "how is my career")
    assert res.ok and not res.refined and res.text == DRAFT


@pytest.mark.asyncio
async def test_pass_with_trailing_text_still_passthrough(monkeypatch):
    monkeypatch.setattr(vs, "get_llm_client", lambda: _client_returning("PASS — well grounded"))
    res = await vs.review_reading(DRAFT, "BLOCKS", "how is my career")
    assert res.ok and res.text == DRAFT


@pytest.mark.asyncio
async def test_refine_applied(monkeypatch):
    refined = ("**In plain language**\nYour career rises through disciplined effort.\n\n"
               "**The astrology behind this**\nExalted Saturn in the 10th drives this.")
    monkeypatch.setattr(vs, "get_llm_client", lambda: _client_returning(refined))
    res = await vs.review_reading(DRAFT, "BLOCKS", "how is my career")
    assert not res.ok and res.refined and res.text == refined


@pytest.mark.asyncio
async def test_degrades_to_draft_on_error(monkeypatch):
    monkeypatch.setattr(vs, "get_llm_client", lambda: _client_raising())
    res = await vs.review_reading(DRAFT, "BLOCKS", "q")
    assert res.ok and res.text == DRAFT          # reviewer hiccup must never blank the reading


@pytest.mark.asyncio
async def test_short_reviewer_output_keeps_draft(monkeypatch):
    # A too-short / non-reading reply → keep the draft rather than deliver a fragment.
    monkeypatch.setattr(vs, "get_llm_client", lambda: _client_returning("looks fine"))
    res = await vs.review_reading(DRAFT, "BLOCKS", "q")
    assert res.ok and res.text == DRAFT
