"""Smoke-import test — catches broken/missing imports the unit tests don't exercise.

Importing `main` pulls in the full router → service → util chain (e.g.
prompt_builder → dasha_analyzer), so a bad import anywhere in it fails here instead of
only at server startup.
"""
import importlib

import pytest

_MODULES = [
    "main",
    "routers.chat",
    "routers.chart",
    "routers.user",
    "services.prompt_builder",
    "services.dasha_analyzer",
    "services.topic_pipeline",
    "services.significator_engine",
    "services.assessment_engine",
    "services.life_overview",
    "services.chart_signatures",
    "services.coverage",
    "services.faithfulness",
    "services.chart_service",
    "services.intent_classifier",
    "services.rule_engine.engine",
    "services.rule_engine.strength_engine",
    "utils.chart_normalizer",
]


@pytest.mark.parametrize("module", _MODULES)
def test_module_imports(module):
    assert importlib.import_module(module) is not None
