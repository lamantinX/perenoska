from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.schemas import CategoryAttribute, CategoryNode, ProductDetails


class MappingService:
    FIELD_SYNONYMS = {
        "бренд": ["brand", "бренд"],
        "цвет": ["color", "цвет"],
        "размер": ["size", "размер", "размер одежды", "tech size", "wbsize"],
        "материал": ["material", "материал"],
        "пол": ["gender", "пол"],
        "страна производства": ["country", "страна производства", "страна изготовитель"],
        "состав": ["composition", "состав"],
    }

    def auto_match_category(
        self,
        source_product: ProductDetails,
        target_categories: list[CategoryNode],
    ) -> CategoryNode | None:
        source_name = self._normalize(source_product.category_name or "")
        if not source_name:
            return None
        best_match: CategoryNode | None = None
        best_score = 0.0
        for category in target_categories:
            score = SequenceMatcher(None, source_name, self._normalize(category.name)).ratio()
            if score > best_score:
                best_score = score
                best_match = category
        return best_match if best_score >= 0.6 else None

    def build_import_payload(
        self,
        *,
        source_product: ProductDetails,
        target_category: CategoryNode,
        target_attributes: list[CategoryAttribute],
        target_marketplace: str,
    ) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str], list[str]]:
        source_index = self._index_source_attributes(source_product)
        mapped_attributes: dict[str, Any] = {}
        payload_attributes: list[tuple[CategoryAttribute, list[dict[str, Any]]]] = []
        missing_required: list[str] = []
        missing_critical: list[str] = []
        warnings: list[str] = []

        for attribute in target_attributes:
            source_value = self._find_source_value(attribute.name, source_index, source_product)
            if source_value is None and target_marketplace == "ozon":
                source_value = self._ozon_attribute_fallback(attribute.name, source_product, target_category)
            if source_value is None:
                if attribute.required:
                    missing_required.append(attribute.name)
                continue
            mapped_value = self._map_value(attribute, source_value)
            if (
                target_marketplace == "ozon"
                and self._requires_ozon_dictionary_match(attribute)
                and not any(item["dictionary_value_id"] for item in mapped_value)
            ):
                if attribute.required:
                    missing_required.append(attribute.name)
                warnings.append(
                    f'Ozon dictionary match not found for "{attribute.name}": {", ".join(source_value)}'
                )
            mapped_attributes[attribute.name] = mapped_value
            payload_attributes.append((attribute, mapped_value))

        if source_product.brand and "бренд" not in source_index:
            warnings.append("Бренд взят из отдельного поля карточки, а не из списка атрибутов.")

        if target_marketplace == "ozon":
            barcode = source_product.barcode_list[0] if source_product.barcode_list else None
            stock = source_product.stock if source_product.stock is not None else 0
            resolved_type_id = self._resolve_ozon_type_id(target_category)
            resolved_type_name = self._resolve_ozon_type_name(target_category)
            if not source_product.offer_id:
                missing_critical.append("offer_id")
            if not source_product.title:
                missing_critical.append("name")
            if not source_product.price:
                missing_critical.append("price")
            if not resolved_type_id:
                missing_critical.append("type_id")
            if not source_product.images:
                warnings.append("У товара нет изображений для Ozon.")
            if not barcode:
                warnings.append("У товара нет штрихкода; для Ozon это нежелательно.")
            payload = {
                "offer_id": self._sanitize_offer_id(source_product.offer_id or source_product.id),
                "name": self._sanitize_ozon_name(source_product.title),
                "description": source_product.description or "",
                "description_category_id": target_category.id,
                "type_id": int(resolved_type_id) if resolved_type_id else 0,
                "attributes": [self._ozon_attribute_payload(attribute, mapped_value) for attribute, mapped_value in payload_attributes],
                "images": source_product.images[:10],
                "price": source_product.price or "0",
                "old_price": source_product.price or "0",
                "stock": stock,
                "barcode": barcode or "",
                "vat": "0",
                **self._ozon_dimensions(source_product),
            }
        else:
            normalized_sizes = self._wb_sizes(source_product)
            if not (source_product.offer_id or source_product.id):
                missing_critical.append("vendorCode")
            if not source_product.title:
                missing_critical.append("title")
            if not source_product.description:
                missing_critical.append("description")
            if not normalized_sizes:
                missing_critical.append("sizes")
            else:
                if any(not size.get("price") for size in normalized_sizes):
                    missing_critical.append("sizes.price")
                if any(not size.get("skus") for size in normalized_sizes):
                    missing_critical.append("sizes.skus")
            payload = {
                "subjectID": target_category.id,
                "variants": [
                    {
                        "vendorCode": source_product.offer_id or source_product.id,
                        "title": self._sanitize_wb_title(source_product.title),
                        "description": source_product.description or "",
                        "brand": source_product.brand or "Нет бренда",
                        "characteristics": [self._attribute_payload(attribute, mapped_value) for attribute, mapped_value in payload_attributes],
                        "sizes": normalized_sizes,
                    }
                ],
            }
        return payload, mapped_attributes, missing_required, missing_critical, warnings

    def _index_source_attributes(self, product: ProductDetails) -> dict[str, list[str]]:
        index: dict[str, list[str]] = {}
        for name, values in product.attributes.items():
            index[self._normalize(name)] = values
        if product.brand:
            index.setdefault(self._normalize("бренд"), [product.brand])
        for size in product.sizes:
            for key in ("techSize", "wbSize"):
                if size.get(key):
                    index.setdefault(self._normalize("размер"), []).append(str(size[key]))
        return index

    def _find_source_value(
        self,
        target_name: str,
        source_index: dict[str, list[str]],
        product: ProductDetails,
    ) -> list[str] | None:
        normalized_target = self._normalize(target_name)
        if normalized_target in source_index:
            return source_index[normalized_target]
        for canonical, variants in self.FIELD_SYNONYMS.items():
            if normalized_target == self._normalize(canonical):
                for variant in variants:
                    normalized_variant = self._normalize(variant)
                    if normalized_variant in source_index:
                        return source_index[normalized_variant]
        if "бренд" in normalized_target and product.brand:
            return [product.brand]
        return None

    def _map_value(self, attribute: CategoryAttribute, values: list[str]) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        dictionary_index = {
            self._normalize(str(item.get("value") or item.get("name") or "")): item
            for item in attribute.dictionary_values
        }
        for value in values:
            normalized = self._normalize(value)
            if dictionary_index and normalized in dictionary_index:
                dictionary_value = dictionary_index[normalized]
                mapped.append(
                    {
                        "value": value,
                        "dictionary_value_id": dictionary_value.get("id")
                        or dictionary_value.get("dictionary_value_id")
                        or 0,
                    }
                )
            else:
                mapped.append({"value": value, "dictionary_value_id": 0})
        return mapped

    def _attribute_payload(self, attribute: CategoryAttribute, mapped_value: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {"id": attribute.id, "name": attribute.name, "value": [item["value"] for item in mapped_value]}
        if any(item["dictionary_value_id"] for item in mapped_value):
            payload["values"] = mapped_value
        return payload

    def _ozon_attribute_payload(self, attribute: CategoryAttribute, mapped_value: list[dict[str, Any]]) -> dict[str, Any]:
        values: list[dict[str, Any]] = []
        for item in mapped_value:
            payload_item: dict[str, Any] = {"value": item["value"]}
            if item["dictionary_value_id"]:
                payload_item["dictionary_value_id"] = item["dictionary_value_id"]
            values.append(payload_item)
        return {
            "id": attribute.id,
            "complex_id": 0,
            "values": values,
        }

    def _requires_ozon_dictionary_match(self, attribute: CategoryAttribute) -> bool:
        dictionary_id = int(attribute.raw.get("dictionary_id") or 0)
        if not dictionary_id:
            return False
        return attribute.id in {85, 8229}

    def _ozon_dimensions(self, product: ProductDetails) -> dict[str, Any]:
        dimensions = product.dimensions or {}
        height = dimensions.get("height") or 1
        width = dimensions.get("width") or 1
        depth = dimensions.get("depth") or dimensions.get("length") or 1
        weight = dimensions.get("weight") or dimensions.get("weightBrutto") or 100
        if isinstance(weight, float) and weight <= 10:
            weight = round(weight * 1000)
        if isinstance(height, (int, float)) and height <= 500:
            height = round(float(height) * 10)
        if isinstance(width, (int, float)) and width <= 500:
            width = round(float(width) * 10)
        if isinstance(depth, (int, float)) and depth <= 500:
            depth = round(float(depth) * 10)
        return {
            "height": int(height),
            "width": int(width),
            "depth": int(depth),
            "weight": int(weight),
            "dimension_unit": "mm",
            "weight_unit": "g",
        }

    def _wb_sizes(self, product: ProductDetails) -> list[dict[str, Any]]:
        price = product.price or ""
        barcodes = product.barcode_list or []
        sizes = product.sizes or []
        if not sizes:
            return [
                {
                    "techSize": "0",
                    "wbSize": "",
                    "price": price,
                    "skus": barcodes,
                }
            ]
        normalized = []
        for size in sizes:
            normalized.append(
                {
                    "techSize": str(size.get("techSize") or size.get("origName") or size.get("name") or "0"),
                    "wbSize": str(size.get("wbSize") or size.get("name") or ""),
                    "price": str(size.get("price") or price or ""),
                    "skus": [str(item) for item in size.get("skus") or size.get("barcodes") or barcodes],
                }
            )
        return normalized

    def _ozon_attribute_fallback(
        self,
        attribute_name: str,
        source_product: ProductDetails,
        target_category: CategoryNode,
    ) -> list[str] | None:
        normalized_name = self._normalize(attribute_name)
        resolved_type_name = self._resolve_ozon_type_name(target_category)

        if normalized_name == self._normalize("тип") and resolved_type_name:
            return [resolved_type_name]

        if "название модели" in normalized_name:
            if source_product.offer_id:
                return [source_product.offer_id[:200]]
            if source_product.title:
                return [source_product.title[:200]]

        return None

    @staticmethod
    def _resolve_ozon_type_id(target_category: CategoryNode) -> int | None:
        raw = target_category.raw or {}
        resolved = raw.get("_resolved_type_id")
        if resolved:
            return int(resolved)
        for child in raw.get("children") or []:
            if child.get("type_id") and not child.get("disabled"):
                return int(child["type_id"])
        return None

    @staticmethod
    def _resolve_ozon_type_name(target_category: CategoryNode) -> str:
        raw = target_category.raw or {}
        resolved_name = str(raw.get("_resolved_type_name") or "").strip()
        if resolved_name:
            return resolved_name
        for child in raw.get("children") or []:
            if child.get("type_name") and not child.get("disabled"):
                return str(child["type_name"]).strip()
        return ""

    @staticmethod
    def _sanitize_offer_id(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())[:50]
        if cleaned[:1] in {"_", "-"}:
            cleaned = f"SKU{cleaned}"[:50]
        if cleaned[:3].startswith("_") or cleaned[:3].startswith("-"):
            cleaned = f"SKU{cleaned}"[:50]
        return cleaned or "SKU-ITEM"

    @staticmethod
    def _sanitize_ozon_name(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip())[:250]

    @staticmethod
    def _sanitize_wb_title(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip())[:60]

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())
