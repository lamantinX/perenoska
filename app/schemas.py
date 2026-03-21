from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Marketplace(str, Enum):
    WB = "wb"
    OZON = "ozon"
    YANDEX_MARKET = "yandex_market"


class JobStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PreviewItemReadiness(str, Enum):
    READY = "ready"
    NEEDS_MAPPING = "needs_mapping"
    BLOCKED = "blocked"


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
    business_id: int | None = None
    campaign_id: int | None = None

    @model_validator(mode="after")
    def validate_marketplace_credentials(self) -> "ConnectionUpsert":
        if self.marketplace == Marketplace.WB and not self.token:
            raise ValueError("Для Wildberries нужен token.")
        if self.marketplace == Marketplace.OZON and (not self.client_id or not self.api_key):
            raise ValueError("Для Ozon нужны client_id и api_key.")
        if self.marketplace == Marketplace.YANDEX_MARKET and (
            not self.token or self.business_id is None or self.campaign_id is None
        ):
            raise ValueError("Для Yandex Market нужны token, business_id и campaign_id.")
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
    product_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_direction(self) -> "TransferPreviewRequest":
        if self.source_marketplace == self.target_marketplace:
            raise ValueError("Источник и приёмник должны отличаться.")
        return self


class TransferPreviewItem(BaseModel):
    product_id: str
    title: str
    readiness: PreviewItemReadiness = PreviewItemReadiness.READY
    source_category_id: int | None = None
    target_category_id: int | None = None
    target_category_name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    mapped_attributes: dict[str, Any] = Field(default_factory=dict)
    missing_required_attributes: list[str] = Field(default_factory=list)
    missing_critical_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    dictionary_issues: list[dict[str, Any]] = Field(default_factory=list)


class TransferPreviewResponse(BaseModel):
    source_marketplace: Marketplace
    target_marketplace: Marketplace
    ready_to_import: bool
    items: list[TransferPreviewItem]
    dictionary_issues: list[dict[str, Any]] = Field(default_factory=list)
    brand_mappings: list[dict[str, Any]] = Field(default_factory=list)
    category_issues: list[dict[str, Any]] = Field(default_factory=list)


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


class DictionaryMappingItem(BaseModel):
    type: str
    source_value: str = Field(min_length=1)
    target_category_id: int
    target_attribute_id: int
    target_dictionary_value_id: int
    target_dictionary_value: str = Field(min_length=1)


class DictionaryMappingSaveRequest(BaseModel):
    source_marketplace: Marketplace
    target_marketplace: Marketplace
    items: list[DictionaryMappingItem] = Field(min_length=1)


class DictionaryMappingResponse(BaseModel):
    id: int
    type: str
    source_value: str
    source_value_normalized: str
    target_attribute_id: int
    target_dictionary_value_id: int
    target_dictionary_value: str


class AutoMappingResult(BaseModel):
    wb_id: int
    ozon_id: int
    wb_name: str
    ozon_name: str
    confidence: float
    source: str
    alternatives: list[dict[str, Any]] = Field(default_factory=list)


class AutoMappingStatusResponse(BaseModel):
    total_wb_categories: int
    mapped: int
    pending_review: int
    high_confidence: int
    medium_confidence: int
    low_confidence: int


class ReviewQueueItem(BaseModel):
    id: int
    wb_id: int
    wb_name: str
    wb_path: str
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    reason: str
    status: str
    created_at: str


class ReviewResolveRequest(BaseModel):
    ozon_id: int
    ozon_name: str = Field(min_length=1)


class CategoryMappingItem(BaseModel):
    type: str
    source_key: str = Field(min_length=1)
    source_label: str = Field(min_length=1)
    target_key: str = Field(min_length=1)
    target_label: str = Field(min_length=1)
    target_context: dict[str, Any] = Field(default_factory=dict)


class CategoryMappingSaveRequest(BaseModel):
    source_marketplace: Marketplace
    target_marketplace: Marketplace
    items: list[CategoryMappingItem] = Field(min_length=1)


class CategoryMappingResponse(BaseModel):
    id: int
    type: str
    source_key: str
    source_label: str
    target_key: str
    target_label: str
    target_context: dict[str, Any] = Field(default_factory=dict)


class PublicFetchRequest(BaseModel):
    url: str
    limit: int = Field(default=20, ge=1, le=100)


# ---------------------------------------------------------------------------
# Admin panel schemas
# ---------------------------------------------------------------------------


class AdminUserResponse(BaseModel):
    id: int
    email: str
    phone: str | None = None
    is_blocked: bool
    created_at: str
    plan_expires_at: str | None = None
    transfer_limit: int | None = None
    transfer_count: int
    connections: list[str]


class AdminTransferResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    source_marketplace: str
    target_marketplace: str
    status: str
    created_at: str
    updated_at: str
    error_message: str | None = None
    base_token: str | None = None
    external_task_id: str | None = None


class TransfersByDayEntry(BaseModel):
    date: str
    count: int
    errors: int


class TopUserEntry(BaseModel):
    email: str
    count: int


class AdminStatsResponse(BaseModel):
    total_users: int
    total_transfers: int
    today_transfers: int
    successful_transfers: int
    failed_transfers: int
    top_users: list[TopUserEntry]
    transfers_by_day: list[TransfersByDayEntry]


class SystemSettings(BaseModel):
    registration_enabled: bool
    banner_text: str
    default_transfer_limit: int


class AdminUpdateUser(BaseModel):
    phone: str | None = None
    is_blocked: bool | None = None
    plan_expires_at: str | None = None
    transfer_limit: int | None = None


class PaymentHistoryEntry(BaseModel):
    id: int
    plan_name: str
    amount: float
    currency: str
    created_at: str


class AddPaymentEntry(BaseModel):
    plan_name: str
    amount: float
    currency: str = "RUB"


class AdminJobLogEntry(BaseModel):
    id: int
    token: str
    base_token: str
    sequence_no: int
    event_type: str
    operation: str
    request_url: str
    status_code: int | None = None
    duration_ms: int | None = None
    error_text: str | None = None


class AdminUserDetailResponse(AdminUserResponse):
    payment_history: list[PaymentHistoryEntry] = Field(default_factory=list)


class PublicFetchResponse(BaseModel):
    marketplace: str  # "wb", "ozon", "yandex_market"
    source_type: str  # "seller", "product"
    source_id: str
    products: list[ProductSummary]
    total: int
    message: str | None = None
    requires_credentials: bool = False
