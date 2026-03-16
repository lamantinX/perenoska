from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.schemas import (
    JobStatus,
    Marketplace,
    TransferJobResponse,
    TransferLaunchRequest,
    TransferPreviewItem,
    TransferPreviewRequest,
    TransferPreviewResponse,
)
from app.services.catalog import CatalogService
from app.services.connections import ConnectionService
from app.services.container import MarketplaceClientFactory
from app.services.mapping import MappingService


class TransferService:
    def __init__(
        self,
        *,
        database,
        connection_service: ConnectionService,
        catalog_service: CatalogService,
        client_factory: MarketplaceClientFactory,
        mapping_service: MappingService,
    ) -> None:
        self.database = database
        self.connection_service = connection_service
        self.catalog_service = catalog_service
        self.client_factory = client_factory
        self.mapping_service = mapping_service

    async def preview(self, user_id: int, payload: TransferPreviewRequest) -> TransferPreviewResponse:
        target_categories = await self.catalog_service.list_categories(user_id, payload.target_marketplace)
        preview_items: list[TransferPreviewItem] = []
        for product_id in payload.product_ids:
            product = await self.catalog_service.get_product_details(user_id, payload.source_marketplace, product_id)
            product = self._apply_product_overrides(product, payload.product_overrides.get(product_id) or {})
            if payload.target_category_id is not None:
                target_category = next((item for item in target_categories if item.id == payload.target_category_id), None)
            else:
                target_category = self.mapping_service.auto_match_category(product, target_categories)

            warnings: list[str] = []
            price_scope_warning = self._wb_price_scope_warning(user_id, payload.source_marketplace, product.price)
            if price_scope_warning:
                warnings.append(price_scope_warning)
            if target_category is None:
                warnings.append("Не удалось автоматически определить целевую категорию.")
                preview_items.append(
                    TransferPreviewItem(
                        product_id=product.id,
                        title=product.title,
                        source_category_id=product.category_id,
                        warnings=warnings,
                    )
                )
                continue

            target_attributes = await self.catalog_service.get_category_attributes_for_category(
                user_id,
                payload.target_marketplace,
                target_category,
                source_product=product,
                required_only=True,
            )
            import_payload, mapped_attributes, missing_required, missing_critical, mapping_warnings = self.mapping_service.build_import_payload(
                source_product=product,
                target_category=target_category,
                target_attributes=target_attributes,
                target_marketplace=payload.target_marketplace.value,
            )
            warnings.extend(mapping_warnings)
            preview_items.append(
                TransferPreviewItem(
                    product_id=product.id,
                    title=product.title,
                    source_category_id=product.category_id,
                    target_category_id=target_category.id,
                    target_category_name=target_category.name,
                    payload=import_payload,
                    mapped_attributes=mapped_attributes,
                    missing_required_attributes=missing_required,
                    missing_critical_fields=missing_critical,
                    warnings=warnings,
                )
            )

        ready = all(
            item.target_category_id is not None
            and not item.missing_required_attributes
            and not item.missing_critical_fields
            for item in preview_items
        )
        return TransferPreviewResponse(
            source_marketplace=payload.source_marketplace,
            target_marketplace=payload.target_marketplace,
            ready_to_import=ready,
            items=preview_items,
        )

    def _apply_product_overrides(self, product, overrides: dict) -> object:
        if not overrides:
            return product
        normalized = {}
        if overrides.get("price") not in {None, ""}:
            normalized["price"] = str(overrides["price"]).strip()
        if overrides.get("stock") not in {None, ""}:
            normalized["stock"] = int(overrides["stock"])
        if overrides.get("brand") not in {None, ""}:
            normalized["brand"] = str(overrides["brand"]).strip()
        if overrides.get("title") not in {None, ""}:
            normalized["title"] = str(overrides["title"]).strip()
        if overrides.get("offer_id") not in {None, ""}:
            normalized["offer_id"] = str(overrides["offer_id"]).strip()
        return product.model_copy(update=normalized) if normalized else product

    def _wb_price_scope_warning(self, user_id: int, source_marketplace: Marketplace, price: str | None) -> str | None:
        if source_marketplace != Marketplace.WB or price:
            return None
        try:
            credentials = self.connection_service.get_credentials(user_id, Marketplace.WB)
            scope = self._extract_wb_scope(credentials.get("token") or "")
        except Exception:
            return None
        if scope is None or scope & 4:
            return None
        return "Цена WB недоступна: текущий token не имеет доступа к API цен и скидок. Нужен новый WB token с price-scope."

    @staticmethod
    def _extract_wb_scope(token: str) -> int | None:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        try:
            data = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
        except Exception:
            return None
        scope = data.get("s")
        return int(scope) if isinstance(scope, int) else None

    async def launch(self, user_id: int, payload: TransferLaunchRequest) -> TransferJobResponse:
        preview = await self.preview(user_id, payload)
        if not preview.ready_to_import:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не все товары готовы к импорту. Сначала исправьте preview.",
            )

        now = datetime.now(UTC).isoformat()
        job = self.database.create_transfer_job(
            user_id=user_id,
            source_marketplace=payload.source_marketplace.value,
            target_marketplace=payload.target_marketplace.value,
            status=JobStatus.PENDING.value,
            payload=preview.model_dump(),
            result={},
            created_at=now,
        )
        target_credentials = self.connection_service.get_credentials(user_id, payload.target_marketplace)
        target_client = self.client_factory.get_client(payload.target_marketplace)
        items = [item.payload for item in preview.items]

        try:
            result = await target_client.create_products(target_credentials, items)
            job = self.database.update_transfer_job(
                job_id=job["id"],
                status=JobStatus.SUBMITTED.value,
                updated_at=datetime.now(UTC).isoformat(),
                external_task_id=result.get("external_task_id") or None,
                result=result,
            )
        except Exception as error:
            job = self.database.update_transfer_job(
                job_id=job["id"],
                status=JobStatus.FAILED.value,
                updated_at=datetime.now(UTC).isoformat(),
                error_message=str(error),
                result={"error": str(error)},
            )
        return self._job_response(job)

    async def sync_status(self, user_id: int, job_id: int) -> TransferJobResponse:
        job = self.database.get_transfer_job(user_id, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")
        if not job.get("external_task_id") and job.get("status") == JobStatus.FAILED.value:
            return self._job_response(job)
        target_marketplace = Marketplace(job["target_marketplace"])
        target_credentials = self.connection_service.get_credentials(user_id, target_marketplace)
        target_client = self.client_factory.get_client(target_marketplace)
        result = await target_client.get_import_status(target_credentials, job.get("external_task_id"))

        remote_status = str(result.get("status") or "").lower()
        if remote_status in {"completed", "success", "done"}:
            status_value = JobStatus.COMPLETED.value
        elif remote_status in {"failed", "error", "unknown"}:
            status_value = JobStatus.FAILED.value
        else:
            status_value = JobStatus.PROCESSING.value

        job = self.database.update_transfer_job(
            job_id=job_id,
            status=status_value,
            updated_at=datetime.now(UTC).isoformat(),
            result=result,
            error_message=self._result_error_message(result),
        )
        return self._job_response(job)

    def list_jobs(self, user_id: int) -> list[TransferJobResponse]:
        jobs = self.database.list_transfer_jobs(user_id)
        return [self._job_response(job) for job in jobs]

    def get_job(self, user_id: int, job_id: int) -> TransferJobResponse:
        job = self.database.get_transfer_job(user_id, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")
        return self._job_response(job)

    def _job_response(self, job: dict) -> TransferJobResponse:
        return TransferJobResponse(
            id=job["id"],
            source_marketplace=Marketplace(job["source_marketplace"]),
            target_marketplace=Marketplace(job["target_marketplace"]),
            status=JobStatus(job["status"]),
            external_task_id=job.get("external_task_id"),
            error_message=job.get("error_message"),
            created_at=job["created_at"],
            updated_at=job["updated_at"],
            payload=job["payload_json"],
            result=job["result_json"],
        )

    @staticmethod
    def _result_error_message(result: dict) -> str | None:
        if result.get("message"):
            return str(result["message"])
        errors = result.get("errors") or []
        if not errors:
            return None
        first = errors[0]
        if isinstance(first, dict):
            return str(first.get("message") or first.get("description") or first.get("code") or "Import error")
        return str(first)
