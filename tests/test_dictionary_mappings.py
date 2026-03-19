from __future__ import annotations

import json

from app.db import Database


def test_dictionary_mapping_roundtrip(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()

    mapping_id = database.save_dictionary_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="brand",
        source_value_raw="Все на удачу",
        source_value_normalized="все на удачу",
        target_attribute_id=85,
        target_dictionary_value_id=111,
        target_dictionary_value="Все на удачу",
        now="2026-03-17T10:00:00+00:00",
    )

    saved = database.get_dictionary_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="brand",
        source_value_normalized="все на удачу",
    )

    assert mapping_id > 0
    assert saved is not None
    assert saved["target_dictionary_value_id"] == 111
    assert saved["target_dictionary_value"] == "Все на удачу"


def test_dictionary_mapping_upsert_updates_existing_rule(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()

    first_id = database.save_dictionary_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="brand",
        source_value_raw="Все на удачу",
        source_value_normalized="все на удачу",
        target_attribute_id=85,
        target_dictionary_value_id=111,
        target_dictionary_value="Все на удачу",
        now="2026-03-17T10:00:00+00:00",
    )

    second_id = database.save_dictionary_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="brand",
        source_value_raw="Все на удачу",
        source_value_normalized="все на удачу",
        target_attribute_id=85,
        target_dictionary_value_id=222,
        target_dictionary_value="Все для удачи",
        now="2026-03-17T11:00:00+00:00",
    )

    saved = database.get_dictionary_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="brand",
        source_value_normalized="все на удачу",
    )

    assert second_id == first_id
    assert saved is not None
    assert saved["target_dictionary_value_id"] == 222
    assert saved["target_dictionary_value"] == "Все для удачи"


def test_category_mapping_roundtrip(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()

    mapping_id = database.save_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="category",
        source_marketplace="wb",
        target_marketplace="ozon",
        source_key="wb:10",
        source_label="T-shirts",
        source_context={},
        target_key="ozon:501",
        target_label="T-shirts",
        target_context={"description_category_id": 501, "type_id": 601, "type_name": "T-shirt"},
        now="2026-03-17T12:00:00+00:00",
    )

    saved = database.get_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="category",
        source_key="wb:10",
    )

    assert mapping_id > 0
    assert saved is not None
    assert saved["target_key"] == "ozon:501"
    assert json.loads(saved["target_context_json"])["type_id"] == 601


def test_dictionary_mapping_is_persisted_in_generalized_mappings_table(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()

    mapping_id = database.save_dictionary_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="brand",
        source_value_raw="Acme",
        source_value_normalized="acme",
        target_attribute_id=85,
        target_dictionary_value_id=111,
        target_dictionary_value="Acme",
        now="2026-03-17T13:00:00+00:00",
    )

    saved = database.get_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="dictionary_brand",
        source_key="brand:acme",
    )

    assert mapping_id == saved["id"]
    assert saved["target_key"] == "dict:111"
    assert json.loads(saved["target_context_json"])["attribute_id"] == 85


def test_dictionary_mapping_reader_can_read_generalized_mapping(tmp_path):
    database = Database(tmp_path / "test.db")
    database.initialize()

    database.save_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="dictionary_brand",
        source_marketplace="wb",
        target_marketplace="ozon",
        source_key="brand:acme",
        source_label="Acme",
        source_context={},
        target_key="dict:111",
        target_label="Acme",
        target_context={"attribute_id": 85},
        now="2026-03-17T13:10:00+00:00",
    )

    saved = database.get_dictionary_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="brand",
        source_value_normalized="acme",
    )

    assert saved is not None
    assert saved["target_dictionary_value_id"] == 111
    assert saved["target_dictionary_value"] == "Acme"
