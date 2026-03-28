"""Unit tests for MappingService.build_import_payload() — TC-1..TC-10."""
from __future__ import annotations

import pytest

from app.schemas import CategoryAttribute, CategoryNode, ProductDetails
from app.services.mapping import MappingService


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_category(category_id: int = 17028727, type_id: int = 94765) -> CategoryNode:
    return CategoryNode(
        id=category_id,
        name="Футболки",
        raw={
            "_resolved_type_id": type_id,
            "_resolved_type_name": "Футболка",
        },
    )


def _make_wb_category(category_id: int = 315) -> CategoryNode:
    return CategoryNode(id=category_id, name="Футболки")


def _call_wb_to_ozon(
    source: ProductDetails,
    attributes: list[CategoryAttribute] | None = None,
) -> tuple:
    svc = MappingService()
    return svc.build_import_payload(
        source_product=source,
        target_category=_make_category(),
        target_attributes=attributes or [],
        target_marketplace="ozon",
    )


def _call_ozon_to_wb(
    source: ProductDetails,
    attributes: list[CategoryAttribute] | None = None,
) -> tuple:
    svc = MappingService()
    return svc.build_import_payload(
        source_product=source,
        target_category=_make_wb_category(),
        target_attributes=attributes or [],
        target_marketplace="wb",
    )


# ---------------------------------------------------------------------------
# Fixtures described in plan-test.md
# ---------------------------------------------------------------------------

@pytest.fixture()
def wb_card_with_description() -> ProductDetails:
    return ProductDetails(
        id="12345678",
        offer_id="ART-001",
        title="Футболка мужская",
        description="Лёгкая хлопковая футболка",
        brand="Nike",
        category_id=315,
        images=["https://basket-01.wbbasket.ru/test/1.webp"],
    )


@pytest.fixture()
def ozon_card_with_annotation() -> ProductDetails:
    return ProductDetails(
        id="ART-001",
        offer_id="ART-001",
        title="Футболка мужская Ozon",
        description="Описание товара из Ozon",
        brand="Nike",
        category_id=17028727,
    )


@pytest.fixture()
def wb_card_with_images() -> ProductDetails:
    return ProductDetails(
        id="12345679",
        offer_id="ART-002",
        title="Футболка",
        description="Описание",
        brand="Adidas",
        images=[
            "https://basket-01.wbbasket.ru/test/1.webp",
            "https://basket-01.wbbasket.ru/test/2.webp",
        ],
    )


@pytest.fixture()
def wb_card_with_attributes() -> ProductDetails:
    return ProductDetails(
        id="12345681",
        offer_id="ART-004",
        title="Футболка с атрибутами",
        description="Описание",
        brand="Nike",
        attributes={
            "Цвет": ["Белый"],
            "Состав": ["Хлопок 100%"],
        },
        images=["https://basket-01.wbbasket.ru/test/1.webp"],
    )


@pytest.fixture()
def ozon_card_with_attributes() -> ProductDetails:
    return ProductDetails(
        id="ART-002",
        offer_id="ART-002",
        title="Футболка с атрибутами",
        description="Описание",
        brand="Nike",
        category_id=17028727,
        attributes={
            "Бренд": ["Nike"],
            "Цвет": ["Белый"],
        },
        images=["https://cdn.ozon.ru/test/1.jpg"],
    )


# ---------------------------------------------------------------------------
# TC-1: WB→Ozon: description → annotation
# ---------------------------------------------------------------------------

def test_tc1_wb_to_ozon_description_mapped_to_annotation(wb_card_with_description):
    payload, *_ = _call_wb_to_ozon(wb_card_with_description)
    assert "annotation" in payload, "payload must have 'annotation' key"
    assert "description" not in payload, "payload must NOT have 'description' key"
    assert payload["annotation"] == "Лёгкая хлопковая футболка"


# ---------------------------------------------------------------------------
# TC-2: WB→Ozon: vendorCode → offer_id
# ---------------------------------------------------------------------------

def test_tc2_wb_to_ozon_vendor_code_mapped_to_offer_id(wb_card_with_description):
    payload, *_ = _call_wb_to_ozon(wb_card_with_description)
    assert payload["offer_id"] == "ART-001"


# ---------------------------------------------------------------------------
# TC-3: WB→Ozon: title → name
# ---------------------------------------------------------------------------

def test_tc3_wb_to_ozon_title_mapped_to_name(wb_card_with_description):
    payload, *_ = _call_wb_to_ozon(wb_card_with_description)
    assert payload["name"] == "Футболка мужская"


# ---------------------------------------------------------------------------
# TC-4: WB→Ozon: images from source_product.images → payload["images"]
# ---------------------------------------------------------------------------

def test_tc4_wb_to_ozon_images_transferred(wb_card_with_images):
    payload, _, _, missing_critical, _ = _call_wb_to_ozon(wb_card_with_images)
    assert payload["images"] == [
        "https://basket-01.wbbasket.ru/test/1.webp",
        "https://basket-01.wbbasket.ru/test/2.webp",
    ]
    assert "images" not in missing_critical


def test_tc4_wb_to_ozon_missing_images_in_critical():
    """When source has no images, 'images' must appear in missing_critical."""
    card = ProductDetails(
        id="12345680",
        offer_id="ART-003",
        title="Товар без фото",
        description="Описание",
        brand="BrandX",
        images=[],
    )
    _, _, _, missing_critical, warnings = _call_wb_to_ozon(card)
    assert "images" in missing_critical
    assert any("изображений" in w for w in warnings)


# ---------------------------------------------------------------------------
# TC-5: Ozon→WB: annotation (stored in .description) → WB description
# ---------------------------------------------------------------------------

def test_tc5_ozon_to_wb_annotation_mapped_to_description(ozon_card_with_annotation):
    payload, *_ = _call_ozon_to_wb(ozon_card_with_annotation)
    variants = payload["variants"]
    assert len(variants) == 1
    assert variants[0]["description"] == "Описание товара из Ozon"


# ---------------------------------------------------------------------------
# TC-6: Ozon→WB: name → title
# ---------------------------------------------------------------------------

def test_tc6_ozon_to_wb_name_mapped_to_title(ozon_card_with_annotation):
    payload, *_ = _call_ozon_to_wb(ozon_card_with_annotation)
    assert payload["variants"][0]["title"] == "Футболка мужская Ozon"


# ---------------------------------------------------------------------------
# TC-7: Ozon payload must NOT contain is_visible or status
# ---------------------------------------------------------------------------

def test_tc7_ozon_payload_no_is_visible_or_status(wb_card_with_description):
    payload, *_ = _call_wb_to_ozon(wb_card_with_description)
    assert "is_visible" not in payload
    assert "status" not in payload


# ---------------------------------------------------------------------------
# TC-8: WB payload must NOT contain publication status field
# ---------------------------------------------------------------------------

def test_tc8_wb_payload_no_status_field(ozon_card_with_annotation):
    payload, *_ = _call_ozon_to_wb(ozon_card_with_annotation)
    assert "status" not in payload
    assert "is_published" not in payload
    assert "is_visible" not in payload
    # check nested variants too
    for variant in payload.get("variants", []):
        assert "status" not in variant
        assert "is_published" not in variant


# ---------------------------------------------------------------------------
# TC-9: WB→Ozon attribute mapping via FIELD_SYNONYMS; unmapped → missing_required
# ---------------------------------------------------------------------------

def test_tc9_wb_to_ozon_attributes_mapped_via_synonyms(wb_card_with_attributes):
    target_attributes = [
        CategoryAttribute(id=10, name="Цвет", required=False),
        CategoryAttribute(id=11, name="Состав", required=False),
        CategoryAttribute(id=12, name="Сезон", required=True),  # no source value → missing_required
    ]
    payload, mapped_attributes, missing_required, _, _ = _call_wb_to_ozon(
        wb_card_with_attributes, attributes=target_attributes
    )
    # Mapped attributes should contain "Цвет" and "Состав"
    assert "Цвет" in mapped_attributes
    assert "Состав" in mapped_attributes
    # "Сезон" has no source value and is required → must be in missing_required
    assert "Сезон" in missing_required
    # payload attributes list must include the mapped ones
    attr_names = {a["id"] for a in payload["attributes"]}
    assert 10 in attr_names  # Цвет
    assert 11 in attr_names  # Состав


# ---------------------------------------------------------------------------
# TC-10: Ozon→WB attribute mapping; unmapped → missing_required
# ---------------------------------------------------------------------------

def test_tc10_ozon_to_wb_attributes_mapped(ozon_card_with_attributes):
    target_attributes = [
        CategoryAttribute(id=20, name="Бренд", required=False),
        CategoryAttribute(id=21, name="Цвет", required=False),
        CategoryAttribute(id=22, name="Материал", required=True),  # absent in source → missing_required
    ]
    payload, mapped_attributes, missing_required, _, _ = _call_ozon_to_wb(
        ozon_card_with_attributes, attributes=target_attributes
    )
    assert "Бренд" in mapped_attributes
    assert "Цвет" in mapped_attributes
    assert "Материал" in missing_required
    # characteristics list in the variant
    char_ids = {c["id"] for c in payload["variants"][0]["characteristics"]}
    assert 20 in char_ids  # Бренд
    assert 21 in char_ids  # Цвет
