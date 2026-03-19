from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from app.schemas import CategoryAttribute, CategoryNode, ProductDetails, ProductSummary


class MarketplaceAPIError(RuntimeError):
    pass


_current_trace_context: ContextVar[Any | None] = ContextVar("current_trace_context", default=None)


@contextmanager
def use_trace_context(trace: Any | None):
    token = _current_trace_context.set(trace)
    try:
        yield
    finally:
        _current_trace_context.reset(token)


def get_trace_context() -> Any | None:
    return _current_trace_context.get()


class MarketplaceClient(ABC):
    @abstractmethod
    async def list_products(self, credentials: dict[str, Any], *, limit: int = 500) -> list[ProductSummary]:
        raise NotImplementedError

    @abstractmethod
    async def get_product_details(self, credentials: dict[str, Any], product_id: str) -> ProductDetails:
        raise NotImplementedError

    @abstractmethod
    async def list_categories(
        self,
        credentials: dict[str, Any],
        *,
        parent_id: int | None = None,
    ) -> list[CategoryNode]:
        raise NotImplementedError

    @abstractmethod
    async def get_category_attributes(
        self,
        credentials: dict[str, Any],
        category_id: int,
        *,
        required_only: bool = False,
    ) -> list[CategoryAttribute]:
        raise NotImplementedError

    @abstractmethod
    async def create_products(self, credentials: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_import_status(
        self,
        credentials: dict[str, Any],
        external_task_id: str | None,
    ) -> dict[str, Any]:
        raise NotImplementedError

