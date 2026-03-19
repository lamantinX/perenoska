from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_catalog_service, get_container, get_current_user
from app.schemas import (
    CategoryMappingResponse,
    CategoryMappingSaveRequest,
    DictionaryMappingResponse,
    DictionaryMappingSaveRequest,
    Marketplace,
)

router = APIRouter(prefix="/mappings", tags=["mappings"])


def _resolve_target_category_id(payload: CategoryMappingSaveRequest, item) -> int:
    if payload.target_marketplace == Marketplace.WB:
        return int(item.target_context.get("subject_id") or str(item.target_key).partition(":")[2] or 0)
    if payload.target_marketplace == Marketplace.YANDEX_MARKET:
        return int(
            item.target_context.get("market_category_id")
            or item.target_context.get("category_id")
            or str(item.target_key).partition(":")[2]
            or 0
        )
    return int(item.target_context.get("description_category_id") or 0)


@router.post("/categories", response_model=list[CategoryMappingResponse])
async def save_category_mappings(
    payload: CategoryMappingSaveRequest,
    user=Depends(get_current_user),
    container=Depends(get_container),
    catalog_service=Depends(get_catalog_service),
) -> list[CategoryMappingResponse]:
    source_connection = container.database.get_connection(user["id"], payload.source_marketplace.value)
    target_connection = container.database.get_connection(user["id"], payload.target_marketplace.value)
    if source_connection is None or target_connection is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сначала настройте оба подключения для сохранения сопоставлений.",
        )

    target_categories = await catalog_service.list_categories(user["id"], payload.target_marketplace)
    saved: list[CategoryMappingResponse] = []

    for item in payload.items:
        target_category_id = _resolve_target_category_id(payload, item)
        target_category = next((candidate for candidate in target_categories if candidate.id == target_category_id), None)
        if target_category is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Целевая категория {target_category_id or item.target_key} не найдена.",
            )

        if payload.target_marketplace == Marketplace.OZON:
            type_id = int(item.target_context.get("type_id") or 0)
            valid_type_ids = {
                int(child["type_id"])
                for child in target_category.raw.get("children") or []
                if child.get("type_id") and not child.get("disabled")
            }
            if type_id not in valid_type_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Выбранный тип Ozon не подходит для указанной категории.",
                )

        mapping_id = container.database.save_mapping(
            source_connection_id=source_connection["id"],
            target_connection_id=target_connection["id"],
            mapping_type=item.type,
            source_marketplace=payload.source_marketplace.value,
            target_marketplace=payload.target_marketplace.value,
            source_key=item.source_key,
            source_label=item.source_label,
            source_context={},
            target_key=item.target_key,
            target_label=item.target_label,
            target_context=item.target_context,
            now=datetime.now(UTC).isoformat(),
        )
        saved.append(
            CategoryMappingResponse(
                id=mapping_id,
                type=item.type,
                source_key=item.source_key,
                source_label=item.source_label,
                target_key=item.target_key,
                target_label=item.target_label,
                target_context=item.target_context,
            )
        )
    return saved


@router.post("/dictionary", response_model=list[DictionaryMappingResponse])
async def save_dictionary_mappings(
    payload: DictionaryMappingSaveRequest,
    user=Depends(get_current_user),
    container=Depends(get_container),
    catalog_service=Depends(get_catalog_service),
) -> list[DictionaryMappingResponse]:
    source_connection = container.database.get_connection(user["id"], payload.source_marketplace.value)
    target_connection = container.database.get_connection(user["id"], payload.target_marketplace.value)
    if source_connection is None or target_connection is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сначала настройте оба подключения для сохранения сопоставлений.",
        )

    if payload.target_marketplace not in {Marketplace.OZON, Marketplace.YANDEX_MARKET}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ручные dictionary mappings поддерживаются только для Ozon и Yandex Market.",
        )

    target_categories = await catalog_service.list_categories(user["id"], payload.target_marketplace)
    target_client = container.client_factory.get_client(payload.target_marketplace)
    target_credentials = container.connection_service.get_credentials(user["id"], payload.target_marketplace)
    saved: list[DictionaryMappingResponse] = []

    for item in payload.items:
        category = next((candidate for candidate in target_categories if candidate.id == item.target_category_id), None)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Целевая категория {item.target_category_id} не найдена.",
            )

        if payload.target_marketplace == Marketplace.OZON:
            resolve_category_context = getattr(target_client, "resolve_category_context", None)
            if callable(resolve_category_context):
                context = resolve_category_context(category)
            else:
                children = [child for child in category.raw.get("children") or [] if child.get("type_id") and not child.get("disabled")]
                context = {"type_id": children[0]["type_id"] if children else None}
            type_id = context.get("type_id")
            if not type_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Для категории {item.target_category_id} не удалось определить type_id Ozon.",
                )

            get_dictionary_values = getattr(target_client, "get_dictionary_values", None)
            if not callable(get_dictionary_values):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Текущий клиент Ozon не поддерживает поиск значений словаря.",
                )

            options = await get_dictionary_values(
                target_credentials,
                attribute_id=item.target_attribute_id,
                description_category_id=category.id,
                type_id=type_id,
                search=item.target_dictionary_value,
                limit=50,
            )
            matched_option = next(
                (option for option in options if int(option.get("id") or 0) == item.target_dictionary_value_id),
                None,
            )
            if matched_option is None:
                options = await get_dictionary_values(
                    target_credentials,
                    attribute_id=item.target_attribute_id,
                    description_category_id=category.id,
                    type_id=type_id,
                    search=None,
                    limit=200,
                )
                matched_option = next(
                    (option for option in options if int(option.get("id") or 0) == item.target_dictionary_value_id),
                    None,
                )
            if matched_option is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Выбранное значение бренда Ozon не прошло валидацию.",
                )
        else:
            attributes = await catalog_service.get_category_attributes(
                user["id"],
                payload.target_marketplace,
                item.target_category_id,
                required_only=False,
            )
            attribute = next((candidate for candidate in attributes if candidate.id == item.target_attribute_id), None)
            if attribute is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Атрибут {item.target_attribute_id} не найден для Yandex Market category {item.target_category_id}.",
                )
            matched_option = next(
                (
                    option
                    for option in attribute.dictionary_values
                    if int(option.get("id") or option.get("dictionary_value_id") or 0) == item.target_dictionary_value_id
                ),
                None,
            )
            if matched_option is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Выбранное значение Yandex Market не прошло валидацию.",
                )

        normalized_source = container.mapping_service._normalize(item.source_value)
        mapping_id = container.database.save_mapping(
            source_connection_id=source_connection["id"],
            target_connection_id=target_connection["id"],
            mapping_type=f"dictionary_{item.type}",
            source_marketplace=payload.source_marketplace.value,
            target_marketplace=payload.target_marketplace.value,
            source_key=f"{item.type}:{normalized_source}",
            source_label=item.source_value,
            source_context={},
            target_key=f"dict:{item.target_dictionary_value_id}",
            target_label=str(matched_option.get("value") or item.target_dictionary_value),
            target_context={
                "attribute_id": item.target_attribute_id,
                "target_dictionary_value_id": item.target_dictionary_value_id,
                "target_dictionary_value": str(matched_option.get("value") or item.target_dictionary_value),
            },
            now=datetime.now(UTC).isoformat(),
        )
        saved.append(
            DictionaryMappingResponse(
                id=mapping_id,
                type=item.type,
                source_value=item.source_value,
                source_value_normalized=normalized_source,
                target_attribute_id=item.target_attribute_id,
                target_dictionary_value_id=item.target_dictionary_value_id,
                target_dictionary_value=str(matched_option.get("value") or item.target_dictionary_value),
            )
        )
    return saved
