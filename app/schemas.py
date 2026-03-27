from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Marketplace(str, Enum):
    WB = "wb"
    OZON = "ozon"


class JobStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ConnectionUpsert(BaseModel):
    marketplace: Marketplace
    token: str | None = None
    client_id: str | None = None
    api_key: str | None = None

    @model_validator(mode="after")
    def validate_marketplace_credentials(self) -> "ConnectionUpsert":
        if self.marketplace == Marketplace.WB and not self.token:
            raise ValueError("Для Wildberries нужен token.")
        if self.marketplace == Marketplace.OZON and (not self.client_id or not self.api_key):
            raise ValueError("Для Ozon нужны client_id и api_key.")
        return self


class ConnectionResponse(BaseModel):
    marketplace: Marketplace
    is_configured: bool
    masked_fields: dict[str, str]
    updated_at: str | None = None


class ProductSummary(BaseModel):
    id: str
    offer_id: str | None = None
    title: str
    description: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    price: str | None = None
    currency: str | None = None
    stock: int | None = None
    images: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ProductDetails(ProductSummary):
    attributes: dict[str, list[str]] = Field(default_factory=dict)
    dimensions: dict[str, Any] = Field(default_factory=dict)
    sizes: list[dict[str, Any]] = Field(default_factory=list)
    barcode_list: list[str] = Field(default_factory=list)
    brand: str | None = None
    supplier: str | None = None
    supplier_id: int | None = None
    grouped_attributes: list[dict[str, Any]] = Field(default_factory=list)
    seller_info: dict[str, Any] = Field(default_factory=dict)
    raw_sources: dict[str, Any] = Field(default_factory=dict)


class CategoryNode(BaseModel):
    id: int
    name: str
    parent_id: int | None = None
    children: list["CategoryNode"] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class CategoryAttribute(BaseModel):
    id: int
    name: str
    required: bool = False
    type: str | None = None
    dictionary_values: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class TransferPreviewRequest(BaseModel):
    source_marketplace: Marketplace
    target_marketplace: Marketplace
    product_ids: list[str] = Field(min_length=1)
    target_category_id: int | None = None
    product_overrides: dict[str, ProductOverride] | None = None

    @model_validator(mode="after")
    def validate_direction(self) -> "TransferPreviewRequest":
        if self.source_marketplace == self.target_marketplace:
            raise ValueError("Источник и приёмник должны отличаться.")
        return self


class ProductOverride(BaseModel):
    category_id: int | None = None
    brand_id: int | None = None
    price: str | None = None
    attributes: list | None = None


class TransferPreviewItem(BaseModel):
    product_id: str
    title: str
    source_category_id: int | None = None
    target_category_id: int | None = None
    target_category_name: str | None = None
    category_confidence: float | None = None
    category_requires_manual: bool = False
    brand_id_suggestion: int | None = None
    brand_id_requires_manual: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    mapped_attributes: dict[str, Any] = Field(default_factory=dict)
    missing_required_attributes: list[str] = Field(default_factory=list)
    missing_critical_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TransferPreviewResponse(BaseModel):
    source_marketplace: Marketplace
    target_marketplace: Marketplace
    ready_to_import: bool
    items: list[TransferPreviewItem]


class TransferLaunchRequest(TransferPreviewRequest):
    pass


class TransferJobResponse(BaseModel):
    id: int
    source_marketplace: Marketplace
    target_marketplace: Marketplace
    status: JobStatus
    external_task_id: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
