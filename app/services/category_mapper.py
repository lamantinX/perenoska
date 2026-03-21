from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

import numpy as np
from cachetools import TTLCache
from rapidfuzz import fuzz

from app.clients.openrouter import OpenRouterClient
from app.config import Settings
from app.db import Database
from app.schemas import CategoryNode

logger = logging.getLogger(__name__)

# Manual top-level root category mapping (WB root name → related Ozon root names).
# Used to narrow down the search space before fuzzy/embedding matching.
ROOT_CATEGORY_MAP: dict[str, list[str]] = {
    "Женская одежда": ["Одежда", "Женская одежда"],
    "Мужская одежда": ["Одежда", "Мужская одежда"],
    "Детская одежда": ["Одежда", "Детская одежда"],
    "Одежда": ["Одежда", "Женская одежда", "Мужская одежда", "Детская одежда"],
    "Обувь": ["Обувь"],
    "Электроника": ["Электроника", "Смартфоны и гаджеты"],
    "Бытовая техника": ["Бытовая техника"],
    "Дом": ["Дом и сад", "Товары для дома"],
    "Красота": ["Красота и здоровье", "Косметика"],
    "Здоровье": ["Красота и здоровье", "Здоровье"],
    "Продукты": ["Продукты питания"],
    "Книги": ["Книги"],
    "Игрушки": ["Игрушки", "Детские товары"],
    "Спорт": ["Спорт и отдых"],
    "Автотовары": ["Автотовары"],
    "Зоотовары": ["Зоотовары"],
    "Канцтовары": ["Канцтовары"],
    "Аксессуары": ["Аксессуары"],
    "Сумки": ["Сумки и чемоданы"],
}


def _flatten_categories(nodes: list[CategoryNode], path: str = "") -> list[dict[str, Any]]:
    """Flatten a tree of CategoryNode into a flat list with full path."""
    result: list[dict[str, Any]] = []
    for node in nodes:
        full_path = f"{path} / {node.name}" if path else node.name
        result.append({"id": node.id, "name": node.name, "path": full_path, "node": node})
        if node.children:
            result.extend(_flatten_categories(node.children, full_path))
    return result


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("/", " ").split())


class MappingResult:
    __slots__ = ("wb_id", "ozon_id", "wb_name", "ozon_name", "confidence", "source", "alternatives")

    def __init__(
        self,
        *,
        wb_id: int,
        ozon_id: int,
        wb_name: str,
        ozon_name: str,
        confidence: float,
        source: str,
        alternatives: list[dict[str, Any]] | None = None,
    ) -> None:
        self.wb_id = wb_id
        self.ozon_id = ozon_id
        self.wb_name = wb_name
        self.ozon_name = ozon_name
        self.confidence = confidence
        self.source = source
        self.alternatives = alternatives or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "wb_id": self.wb_id,
            "ozon_id": self.ozon_id,
            "wb_name": self.wb_name,
            "ozon_name": self.ozon_name,
            "confidence": self.confidence,
            "source": self.source,
            "alternatives": self.alternatives,
        }


class CategoryMapper:
    def __init__(
        self,
        database: Database,
        openrouter: OpenRouterClient,
        settings: Settings,
    ) -> None:
        self.database = database
        self.openrouter = openrouter
        self.settings = settings
        self._cache: TTLCache = TTLCache(maxsize=8192, ttl=3600)
        self._embed_matrix: np.ndarray | None = None
        self._embed_ids: list[int] = []
        self._embed_names: list[str] = []
        self._embed_paths: list[str] = []
        self._embed_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def map_category(
        self,
        wb_category: CategoryNode,
        ozon_flat: list[dict[str, Any]],
        *,
        wb_path: str = "",
    ) -> MappingResult:
        """Map a single WB category to an Ozon category using the 3-tier pipeline."""
        # L1: in-memory cache
        cached = self._cache.get(wb_category.id)
        if cached is not None:
            return cached

        # L2: database
        existing = self.database.get_category_mapping(wb_category.id)
        if existing is not None and existing["confidence"] >= self.settings.catmatch_llm_min:
            result = MappingResult(
                wb_id=existing["wb_id"],
                ozon_id=existing["ozon_id"],
                wb_name=existing["wb_name"],
                ozon_name=existing["ozon_name"],
                confidence=existing["confidence"],
                source=existing["source"],
                alternatives=json.loads(existing["alternatives"]) if isinstance(existing["alternatives"], str) else existing["alternatives"],
            )
            self._cache[wb_category.id] = result
            return result

        # Pre-filter by root categories
        filtered = self._prefilter(wb_category, ozon_flat)

        # Phase 1: Fuzzy
        result = self._fuzzy_match(wb_category, filtered, wb_path=wb_path)
        if result.confidence >= self.settings.catmatch_fuzzy_min:
            return await self._save(result)

        # Phase 2: Embedding
        if self.settings.openrouter_api_key:
            result = await self._embedding_match(wb_category, filtered, wb_path=wb_path)
            if result.confidence >= self.settings.catmatch_embed_min * 100:
                return await self._save(result)

            # Phase 3: LLM
            result = await self._llm_match(wb_category, filtered[:30], wb_path=wb_path)
            if result.confidence >= self.settings.catmatch_llm_min:
                return await self._save(result)

        # Failed all tiers → manual review
        now = datetime.now(UTC).isoformat()
        self.database.add_to_review_queue(
            wb_id=wb_category.id,
            wb_name=wb_category.name,
            wb_path=wb_path,
            candidates=json.dumps(result.alternatives[:10], ensure_ascii=False),
            reason=f"Low confidence: {result.confidence:.1f}%",
            now=now,
        )
        logger.info("Category %s (%s) sent to manual review (confidence %.1f%%)", wb_category.id, wb_category.name, result.confidence)
        return result

    async def map_categories_batch(
        self,
        wb_categories: list[CategoryNode],
        ozon_categories: list[CategoryNode],
    ) -> list[MappingResult]:
        """Batch mode: map all WB categories to Ozon."""
        ozon_flat = _flatten_categories(ozon_categories)

        # Pre-build embedding matrix once if OpenRouter is configured
        if self.settings.openrouter_api_key:
            await self._ensure_embed_matrix(ozon_flat)

        results: list[MappingResult] = []
        for wb_cat in wb_categories:
            result = await self.map_category(wb_cat, ozon_flat, wb_path=wb_cat.name)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Pre-filter
    # ------------------------------------------------------------------

    def _prefilter(
        self,
        wb_category: CategoryNode,
        ozon_flat: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        wb_lower = wb_category.name.lower()
        matched_roots: list[str] = []
        for wb_root, ozon_roots in ROOT_CATEGORY_MAP.items():
            if wb_root.lower() in wb_lower or wb_lower in wb_root.lower():
                matched_roots.extend(ozon_roots)
        if not matched_roots:
            return ozon_flat
        matched_lower = {r.lower() for r in matched_roots}
        filtered = [
            cat for cat in ozon_flat
            if any(root in cat["path"].lower() for root in matched_lower)
        ]
        return filtered if filtered else ozon_flat

    # ------------------------------------------------------------------
    # Phase 1: Fuzzy matching
    # ------------------------------------------------------------------

    def _fuzzy_match(
        self,
        wb_category: CategoryNode,
        ozon_flat: list[dict[str, Any]],
        *,
        wb_path: str = "",
    ) -> MappingResult:
        query = _normalize(f"{wb_path} {wb_category.name}" if wb_path else wb_category.name)
        scored: list[tuple[dict[str, Any], float]] = []
        for cat in ozon_flat:
            target = _normalize(cat["path"])
            score = fuzz.token_sort_ratio(query, target)
            scored.append((cat, score))
        scored.sort(key=lambda x: x[1], reverse=True)

        best_cat, best_score = scored[0]
        alternatives = [
            {"ozon_id": c["id"], "ozon_name": c["name"], "ozon_path": c["path"], "score": round(s, 1)}
            for c, s in scored[:5]
        ]
        return MappingResult(
            wb_id=wb_category.id,
            ozon_id=best_cat["id"],
            wb_name=wb_category.name,
            ozon_name=best_cat["name"],
            confidence=best_score,
            source="fuzzy",
            alternatives=alternatives,
        )

    # ------------------------------------------------------------------
    # Phase 2: Embedding matching
    # ------------------------------------------------------------------

    async def _ensure_embed_matrix(self, ozon_flat: list[dict[str, Any]]) -> None:
        async with self._embed_lock:
            if self._embed_matrix is not None:
                return
            paths = [cat["path"] for cat in ozon_flat]
            ids = [cat["id"] for cat in ozon_flat]
            names = [cat["name"] for cat in ozon_flat]

            all_embeddings: list[list[float]] = []
            batch_size = 100
            for i in range(0, len(paths), batch_size):
                chunk = paths[i : i + batch_size]
                embeddings = await self.openrouter.get_embeddings(chunk, self.settings.catmatch_embed_model)
                all_embeddings.extend(embeddings)

            self._embed_matrix = np.array(all_embeddings, dtype=np.float32)
            # Normalize rows for cosine similarity
            norms = np.linalg.norm(self._embed_matrix, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)
            self._embed_matrix = self._embed_matrix / norms
            self._embed_ids = ids
            self._embed_names = names
            self._embed_paths = paths

    async def _embedding_match(
        self,
        wb_category: CategoryNode,
        ozon_flat: list[dict[str, Any]],
        *,
        wb_path: str = "",
    ) -> MappingResult:
        query_text = f"{wb_path} / {wb_category.name}" if wb_path else wb_category.name
        wb_embeddings = await self.openrouter.get_embeddings(
            [query_text], self.settings.catmatch_embed_model
        )
        wb_vec = np.array(wb_embeddings[0], dtype=np.float32)
        wb_norm = np.linalg.norm(wb_vec)
        if wb_norm > 0:
            wb_vec = wb_vec / wb_norm

        # If we have a pre-built matrix, use it with index mapping
        if self._embed_matrix is not None:
            # Map filtered ozon_flat ids to matrix indices
            id_to_idx = {oid: i for i, oid in enumerate(self._embed_ids)}
            indices = [id_to_idx[cat["id"]] for cat in ozon_flat if cat["id"] in id_to_idx]
            if indices:
                sub_matrix = self._embed_matrix[indices]
                similarities = sub_matrix @ wb_vec
                top_local = np.argsort(similarities)[::-1][:5]
                best_local = top_local[0]
                best_score = float(similarities[best_local]) * 100
                alternatives = [
                    {
                        "ozon_id": ozon_flat[int(idx)]["id"] if int(idx) < len(ozon_flat) else self._embed_ids[indices[int(idx)]],
                        "ozon_name": ozon_flat[int(idx)]["name"] if int(idx) < len(ozon_flat) else self._embed_names[indices[int(idx)]],
                        "score": round(float(similarities[int(idx)]) * 100, 1),
                    }
                    for idx in top_local
                ]
                best_global_idx = indices[int(best_local)]
                return MappingResult(
                    wb_id=wb_category.id,
                    ozon_id=self._embed_ids[best_global_idx],
                    wb_name=wb_category.name,
                    ozon_name=self._embed_names[best_global_idx],
                    confidence=best_score,
                    source="embedding",
                    alternatives=alternatives,
                )

        # Fallback: embed filtered subset on the fly
        filtered_paths = [cat["path"] for cat in ozon_flat]
        ozon_embeddings = await self.openrouter.get_embeddings(
            filtered_paths, self.settings.catmatch_embed_model
        )
        matrix = np.array(ozon_embeddings, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        matrix = matrix / norms

        similarities = matrix @ wb_vec
        top_indices = np.argsort(similarities)[::-1][:5]
        best_idx = int(top_indices[0])
        best_score = float(similarities[best_idx]) * 100

        alternatives = [
            {
                "ozon_id": ozon_flat[int(idx)]["id"],
                "ozon_name": ozon_flat[int(idx)]["name"],
                "score": round(float(similarities[int(idx)]) * 100, 1),
            }
            for idx in top_indices
        ]
        return MappingResult(
            wb_id=wb_category.id,
            ozon_id=ozon_flat[best_idx]["id"],
            wb_name=wb_category.name,
            ozon_name=ozon_flat[best_idx]["name"],
            confidence=best_score,
            source="embedding",
            alternatives=alternatives,
        )

    # ------------------------------------------------------------------
    # Phase 3: LLM fallback
    # ------------------------------------------------------------------

    async def _llm_match(
        self,
        wb_category: CategoryNode,
        candidates: list[dict[str, Any]],
        *,
        wb_path: str = "",
    ) -> MappingResult:
        candidate_lines = "\n".join(
            f"  {i + 1}. [id={cat['id']}] {cat['path']}"
            for i, cat in enumerate(candidates)
        )
        prompt = (
            "Ты — эксперт по маркетплейсам. Сопоставь категорию Wildberries "
            "с наиболее подходящей категорией Ozon.\n\n"
            f"Категория WB: {wb_category.name}\n"
            f"Путь WB: {wb_path or wb_category.name}\n\n"
            f"Кандидаты Ozon:\n{candidate_lines}\n\n"
            "Ответь строго JSON без пояснений:\n"
            '{"ozon_id": <id>, "confidence": <0-100>, "reason": "..."}'
        )
        try:
            response_text = await self.openrouter.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self.settings.catmatch_llm_model,
            )
            parsed = self.openrouter.parse_json_response(response_text)
            ozon_id = int(parsed["ozon_id"])
            confidence = float(parsed.get("confidence", 50))
            matched = next((c for c in candidates if c["id"] == ozon_id), candidates[0])
        except Exception:
            logger.exception("LLM matching failed for wb_id=%s", wb_category.id)
            # Fall back to best fuzzy candidate
            if candidates:
                matched = candidates[0]
                ozon_id = matched["id"]
                confidence = 0.0
            else:
                return MappingResult(
                    wb_id=wb_category.id, ozon_id=0, wb_name=wb_category.name,
                    ozon_name="", confidence=0.0, source="llm_error",
                )

        alternatives = [
            {"ozon_id": c["id"], "ozon_name": c["name"], "ozon_path": c["path"]}
            for c in candidates[:5]
        ]
        return MappingResult(
            wb_id=wb_category.id,
            ozon_id=ozon_id,
            wb_name=wb_category.name,
            ozon_name=matched["name"],
            confidence=confidence,
            source="llm",
            alternatives=alternatives,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _save(self, result: MappingResult) -> MappingResult:
        now = datetime.now(UTC).isoformat()
        self.database.upsert_category_mapping(
            wb_id=result.wb_id,
            ozon_id=result.ozon_id,
            confidence=result.confidence,
            source=result.source,
            wb_name=result.wb_name,
            ozon_name=result.ozon_name,
            alternatives=json.dumps(result.alternatives, ensure_ascii=False),
            now=now,
        )
        self._cache[result.wb_id] = result
        logger.info(
            "Mapped wb_id=%s → ozon_id=%s (%.1f%%, %s)",
            result.wb_id, result.ozon_id, result.confidence, result.source,
        )
        return result
