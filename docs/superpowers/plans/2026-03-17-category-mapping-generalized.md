# Category Mapping Generalized Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить общую систему persistent mappings для категорий между маркетплейсами с первым рабочим сценарием `WB -> Ozon`, используя выбор из полного списка категорий и обязательный выбор `type_id` для Ozon.

**Architecture:** Backend вводит общую таблицу `mappings`, новый слой category mapping и `category_issues` в preview. Frontend добавляет отдельную modal для сопоставления категорий, работающую по сгруппированным исходным категориям и повторно запускающую preview после сохранения правил.

**Tech Stack:** FastAPI, Pydantic, SQLite в `app/db.py`, встроенный frontend в `app/static/app.js`, pytest.

---

## File Structure

**Core backend**
- Modify: `app/db.py`
- Modify: `app/schemas.py`
- Modify: `app/services/mapping.py`
- Modify: `app/services/transfer.py`
- Modify: `app/clients/ozon.py`
- Modify: `app/api/routes/mappings.py`

**Frontend**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/app.css`

**Tests**
- Modify: `tests/test_dictionary_mappings.py`
- Modify: `tests/test_transfer_preview.py`
- Create if needed: `tests/test_category_mapping.py`

## Task 1: Introduce generalized mappings storage

**Files:**
- Modify: `app/db.py`
- Modify: `tests/test_dictionary_mappings.py`

- [ ] **Step 1: Write failing test for generalized category mapping storage**

```python
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
        target_context={"description_category_id": 501, "type_id": 601},
        now="2026-03-17T12:00:00+00:00",
    )

    saved = database.get_mapping(1, 2, "category", "wb:10")
    assert mapping_id > 0
    assert saved["target_key"] == "ozon:501"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dictionary_mappings.py -k category_mapping -v`
Expected: FAIL because generalized mapping methods/table do not exist yet.

- [ ] **Step 3: Implement generalized mapping table and access methods**

Add a new `mappings` table with JSON columns for contexts and methods:

```python
def save_mapping(...): ...
def get_mapping(...): ...
def list_mappings(...): ...
```

Keep current brand mapping behavior working, either by:
- migrating existing calls to the new methods, or
- keeping `save_dictionary_mapping` as a thin adapter over `save_mapping`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_dictionary_mappings.py -k category_mapping -v`
Expected: PASS

## Task 2: Add preview category issues grouped by source category

**Files:**
- Modify: `app/schemas.py`
- Modify: `app/services/mapping.py`
- Modify: `app/services/transfer.py`
- Modify: `tests/test_transfer_preview.py`

- [ ] **Step 1: Write failing test for category issue grouping**

```python
def test_preview_returns_grouped_category_issues(tmp_path):
    response = client.post("/api/v1/transfers/preview", ...)
    data = response.json()
    assert data["category_issues"] == [
        {
            "type": "category",
            "source_key": "wb:10",
            "source_label": "T-shirts",
            "product_ids": ["1001"],
        }
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transfer_preview.py -k category_issues -v`
Expected: FAIL because preview has no `category_issues`.

- [ ] **Step 3: Implement category issue generation**

Backend rules:
- resolve saved category mapping before auto-match;
- if unresolved, build `category_issues` grouped by source category;
- do not build brand issues for unresolved-category items;
- mark preview as not ready while unresolved category issues exist.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transfer_preview.py -k category_issues -v`
Expected: PASS

## Task 3: Load full target category options for category issues

**Files:**
- Modify: `app/services/transfer.py`
- Modify: `app/clients/ozon.py`
- Modify: `tests/test_transfer_preview.py`

- [ ] **Step 1: Write failing test for category options including Ozon types**

```python
def test_category_issue_contains_full_target_options_for_ozon(tmp_path):
    response = client.post("/api/v1/transfers/preview", ...)
    issue = response.json()["category_issues"][0]
    assert issue["options"][0]["context"]["types"][0]["id"] == 601
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transfer_preview.py -k full_target_options -v`
Expected: FAIL because preview does not hydrate full category options.

- [ ] **Step 3: Implement option hydration**

For `WB -> Ozon`:
- include full list of Ozon categories in each category issue;
- include available `type_id/type_name` options from category context;
- include searchable labels/path strings for UI.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transfer_preview.py -k full_target_options -v`
Expected: PASS

## Task 4: Add category mappings save API

**Files:**
- Modify: `app/api/routes/mappings.py`
- Modify: `app/schemas.py`
- Modify: `tests/test_transfer_preview.py`

- [ ] **Step 1: Write failing API test for category mapping save**

```python
def test_save_category_mapping_for_wb_to_ozon(tmp_path):
    response = client.post("/api/v1/mappings/categories", json=payload)
    assert response.status_code == 200
    assert response.json()[0]["target_context"]["type_id"] == 601
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transfer_preview.py -k save_category_mapping -v`
Expected: FAIL because the endpoint/schema does not exist yet.

- [ ] **Step 3: Implement save endpoint and validation**

Validation rules:
- target category exists;
- for Ozon, selected `type_id` is valid for that category;
- save as `mapping_type="category"` in generalized mappings storage.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transfer_preview.py -k save_category_mapping -v`
Expected: PASS

## Task 5: Apply saved category mapping in preview

**Files:**
- Modify: `app/services/transfer.py`
- Modify: `app/services/mapping.py`
- Modify: `tests/test_transfer_preview.py`

- [ ] **Step 1: Write failing test for saved category mapping reuse**

```python
def test_saved_category_mapping_resolves_preview_before_brand_checks(tmp_path):
    save_mapping(...)
    response = client.post("/api/v1/transfers/preview", ...)
    data = response.json()
    assert data["category_issues"] == []
    assert data["items"][0]["target_category_id"] == 501
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transfer_preview.py -k saved_category_mapping_resolves_preview -v`
Expected: FAIL because saved category mappings are not applied yet.

- [ ] **Step 3: Apply saved category mappings before auto-match**

Rules:
- saved mapping wins over auto-match;
- resolved category enables downstream brand/dictionary mapping;
- unresolved category suppresses brand issues for that item.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transfer_preview.py -k saved_category_mapping_resolves_preview -v`
Expected: PASS

## Task 6: Add category mapping modal in frontend

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/app.css`

- [ ] **Step 1: Add UI state and modal skeleton**

Implement:
- button `Сопоставить категории`;
- modal container;
- local UI state for grouped category issues, selected target category, selected type, search text.

- [ ] **Step 2: Render grouped source categories with full target list**

UI rules:
- group by source category;
- show list of affected products;
- show searchable full target category list;
- if target marketplace is Ozon, show type selector after category selection.

- [ ] **Step 3: Wire save flow**

Frontend actions:
- validate that each unresolved source category has a selected target;
- call `/api/v1/mappings/categories`;
- rerun preview on success;
- hide brand mapping button while category issues still exist.

- [ ] **Step 4: Smoke-check manually in app**

Manual check:
- unresolved category shows category modal button;
- saving category rule resolves category issue on next preview;
- Ozon type is required before save.

## Task 7: Final verification

**Files:**
- Review: all changed files

- [ ] **Step 1: Run targeted tests**

Run: `python -m pytest tests/test_dictionary_mappings.py tests/test_transfer_preview.py -v`
Expected: PASS

- [ ] **Step 2: Run full suite**

Run: `python -m pytest`
Expected: PASS

- [ ] **Step 3: Run verification script**

Run: `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`
Expected: PASS

- [ ] **Step 4: Check repository state**

Run: `git status --short --branch`
Expected: only intended files changed.
