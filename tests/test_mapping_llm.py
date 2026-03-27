"""Tests for MappingService LLM and brand-matching logic.

Covers:
  TC-11 — find_brand_id exact match (case-sensitive)
  TC-12 — find_brand_id case-insensitive
  TC-13 — find_brand_id substring
  TC-14 — find_brand_id not found → (None, False)
  TC-15 — auto_match_category_llm confidence >= 0.7
  TC-16 — auto_match_category_llm confidence < 0.7
  TC-17 — auto_match_category_llm invalid category_id → (None, 0.0)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import AsyncOpenAI

from app.config import Settings
from app.main import create_app
from app.schemas import CategoryNode
from app.services.mapping import MappingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_fake_llm_client(category_id: int = 17028727, confidence: float = 0.92) -> AsyncOpenAI:
    """AsyncOpenAI mock with a fixed JSON response."""
    mock_client = MagicMock(spec=AsyncOpenAI)
    choice = MagicMock()
    choice.message.content = json.dumps({"category_id": category_id, "confidence": confidence})
    completion = MagicMock()
    completion.choices = [choice]
    mock_client.chat.completions.create = AsyncMock(return_value=completion)
    return mock_client


# ozon_categories fixture data: flat list of CategoryNode
OZON_CATEGORIES = [
    CategoryNode(id=17028726, name="Одежда", parent_id=None, raw={}),
    CategoryNode(id=17028727, name="Футболки", parent_id=17028726, raw={"type_id": 94765}),
]


# ---------------------------------------------------------------------------
# TC-15: auto_match_category_llm confidence >= 0.7
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_auto_match_category_llm_high_confidence() -> None:
    """TC-15: returns (CategoryNode, confidence) when LLM confidence >= 0.7."""
    llm_client = make_fake_llm_client(category_id=17028727, confidence=0.92)
    service = MappingService(llm_client=llm_client, llm_model="test-model")

    target_categories = [{"id": c.id, "name": c.name} for c in OZON_CATEGORIES]
    result_node, confidence = await service.auto_match_category_llm("Футболки", target_categories)

    assert result_node is not None
    assert result_node["id"] == 17028727
    assert confidence >= 0.7
    llm_client.chat.completions.create.assert_awaited_once()


# ---------------------------------------------------------------------------
# TC-16: auto_match_category_llm confidence < 0.7
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_auto_match_category_llm_low_confidence() -> None:
    """TC-16: returns (CategoryNode, confidence) with low confidence — signal for category_requires_manual=True."""
    llm_client = make_fake_llm_client(category_id=17028727, confidence=0.45)
    service = MappingService(llm_client=llm_client, llm_model="test-model")

    target_categories = [{"id": c.id, "name": c.name} for c in OZON_CATEGORIES]
    result_node, confidence = await service.auto_match_category_llm("Футболки", target_categories)

    assert result_node is not None
    assert result_node["id"] == 17028727
    assert confidence < 0.7


# ---------------------------------------------------------------------------
# TC-17: auto_match_category_llm invalid category_id → (None, 0.0)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_auto_match_category_llm_invalid_category_id() -> None:
    """TC-17: returns (None, 0.0) when LLM category_id is not in target_categories."""
    llm_client = make_fake_llm_client(category_id=99999999, confidence=0.85)
    service = MappingService(llm_client=llm_client, llm_model="test-model")

    target_categories = [{"id": c.id, "name": c.name} for c in OZON_CATEGORIES]
    result_node, confidence = await service.auto_match_category_llm("Футболки", target_categories)

    assert result_node is None
    assert confidence == 0.0


# ---------------------------------------------------------------------------
# TC-15 extra: MappingService accepts AsyncMock as llm_client without error
# ---------------------------------------------------------------------------


def test_mapping_service_accepts_async_mock_as_llm_client() -> None:
    """TC-15 (DI check): MappingService stores AsyncMock llm_client without error."""
    mock_client = MagicMock(spec=AsyncOpenAI)
    service = MappingService(llm_client=mock_client, llm_model="test-model")
    assert service.llm_client is mock_client
    assert service.llm_model == "test-model"


# ---------------------------------------------------------------------------
# TC-17 extra: ServiceContainer creates llm_client and passes it to MappingService
# ---------------------------------------------------------------------------


def test_service_container_initializes_llm_client(tmp_path: Path) -> None:
    """TC-17 (container): ServiceContainer creates llm_client, MappingService receives it."""
    settings = Settings(
        app_name="test",
        secret_key="test-secret",
        database_path=tmp_path / "test.db",
        session_ttl_hours=24,
        wb_base_url="https://content-api.wildberries.ru",
        ozon_base_url="https://api-seller.ozon.ru",
        http_timeout_seconds=10.0,
        openrouter_api_key="test-key",
        llm_model="test-model",
    )
    app = create_app(settings)
    container = app.state.container
    assert container.llm_client is not None
    assert isinstance(container.llm_client, AsyncOpenAI)
    assert container.mapping_service.llm_client is container.llm_client
    assert container.mapping_service.llm_model == "test-model"


# ---------------------------------------------------------------------------
# TC-11..TC-14: find_brand_id
# ---------------------------------------------------------------------------


def _make_ozon_client_mock(brands: list[dict]) -> MagicMock:
    """Create a mock ozon_client whose list_brands returns the given brands list."""
    mock = MagicMock()
    mock.list_brands = AsyncMock(return_value=brands)
    return mock


@pytest.mark.anyio
async def test_find_brand_id_exact_match() -> None:
    """TC-11: find_brand_id returns brand_id on exact case-sensitive match."""
    service = MappingService()
    ozon_client = _make_ozon_client_mock([{"id": 1000, "name": "Nike"}, {"id": 1001, "name": "Adidas"}])

    brand_id, found = await service.find_brand_id({}, "Nike", ozon_client)

    assert brand_id == 1000
    assert found is True


@pytest.mark.anyio
async def test_find_brand_id_case_insensitive() -> None:
    """TC-12: find_brand_id returns brand_id on case-insensitive match when exact fails."""
    service = MappingService()
    ozon_client = _make_ozon_client_mock([{"id": 1000, "name": "NIKE"}, {"id": 1001, "name": "adidas"}])

    brand_id, found = await service.find_brand_id({}, "Nike", ozon_client)

    assert brand_id == 1000
    assert found is True


@pytest.mark.anyio
async def test_find_brand_id_substring_match() -> None:
    """TC-13: find_brand_id returns brand_id on substring match."""
    service = MappingService()
    ozon_client = _make_ozon_client_mock(
        [{"id": 1000, "name": "Nike Sport Collection"}, {"id": 1001, "name": "Adidas Original"}]
    )

    brand_id, found = await service.find_brand_id({}, "Nike", ozon_client)

    assert brand_id == 1000
    assert found is True


@pytest.mark.anyio
async def test_find_brand_id_not_found() -> None:
    """TC-14: find_brand_id returns (None, False) when brand is not found."""
    service = MappingService()
    ozon_client = _make_ozon_client_mock([])

    brand_id, found = await service.find_brand_id({}, "Nike", ozon_client)

    assert brand_id is None
    assert found is False
