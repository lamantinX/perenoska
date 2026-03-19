# Ozon Brand Dictionary Mapping Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить постоянные ручные сопоставления брендов WB -> Ozon для конкретной пары кабинетов, с отображением unresolved brand issues в preview и поиском по брендам Ozon в модальном окне.

**Architecture:** Backend расширяет preview/import структурированными `dictionary_issues`, хранит постоянные brand mappings в SQLite и отдает API для сохранения ручных соответствий. Frontend добавляет кнопку и модальное окно с searchable dropdown, после сохранения выполняет повторный preview и скрывает закрытые проблемы.

**Tech Stack:** FastAPI, Pydantic, SQLite layer в `app/db.py`, встроенный frontend в `app/static/app.js`, pytest.

---

## File Structure

**Core backend**
- Modify: `app/db.py`
- Modify: `app/schemas.py`
- Modify: `app/services/mapping.py`
- Modify: `app/services/transfer.py`
- Modify: `app/clients/ozon.py`
- Modify or create: `app/api/routes/transfers.py`
- Create or modify: `app/api/routes/mappings.py`

**Frontend**
- Modify: `app/static/app.js`
- Modify: `app/static/app.css`

**Tests**
- Modify or create: `tests/test_db.py`
- Modify or create: `tests/test_mapping.py`
- Modify or create: `tests/test_transfers_api.py`
- Modify or create: `tests/test_ui_preview.py`

## Task 1: Add schema and persistence for dictionary mappings

**Files:**
- Modify: `app/db.py`
- Modify: `app/schemas.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing DB test for brand mapping persistence**

```python
def test_dictionary_mapping_roundtrip(database):
    mapping_id = database.save_dictionary_mapping(
        source_connection_id=1,
        target_connection_id=2,
        mapping_type="brand",
        source_value_raw="Все на удачу",
        source_value_normalized="все на удачу",
        target_attribute_id=85,
        target_dictionary_value_id=111,
        target_dictionary_value="Все на удачу",
    )

    saved = database.get_dictionary_mapping(1, 2, "brand", "все на удачу")

    assert mapping_id
    assert saved["target_dictionary_value_id"] == 111
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py -k dictionary_mapping -v`
Expected: FAIL because the table and repository methods do not exist yet.

- [ ] **Step 3: Add SQLite table and repository methods**

Implement in `app/db.py`:

```python
def save_dictionary_mapping(...): ...
def get_dictionary_mapping(...): ...
def list_dictionary_mappings(...): ...
```

Add table creation with unique constraint on:

```sql
(source_connection_id, target_connection_id, mapping_type, source_value_normalized)
```

Add minimal Pydantic models in `app/schemas.py`:

```python
class DictionaryMappingItem(BaseModel):
    type: str
    source_value: str
    target_attribute_id: int
    target_dictionary_value_id: int
    target_dictionary_value: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py -k dictionary_mapping -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/db.py app/schemas.py tests/test_db.py
git commit -m "feat: persist ozon brand dictionary mappings"
```

## Task 2: Teach mapping service to use persistent brand mappings

**Files:**
- Modify: `app/services/mapping.py`
- Modify: `app/schemas.py`
- Test: `tests/test_mapping.py`

- [ ] **Step 1: Write failing tests for unresolved brand issues and saved lookup**

```python
def test_build_import_payload_returns_brand_dictionary_issue_when_match_missing():
    payload, mapped, missing_required, missing_critical, warnings, issues = service.build_import_payload(...)
    assert issues == [
        {
            "type": "brand",
            "source_value": "Все на удачу",
            "target_attribute_name": "Бренд",
        }
    ]


def test_build_import_payload_uses_saved_brand_mapping():
    payload, mapped, missing_required, missing_critical, warnings, issues = service.build_import_payload(...)
    assert not issues
    assert payload["attributes"][0]["values"][0]["dictionary_value_id"] == 111
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mapping.py -k "dictionary_issue or saved_brand_mapping" -v`
Expected: FAIL because `build_import_payload` does not return structured issues or accept persisted mappings.

- [ ] **Step 3: Extend mapping service contract**

Refactor `app/services/mapping.py` so `build_import_payload` returns:

```python
tuple[
    dict[str, Any],
    dict[str, Any],
    list[str],
    list[str],
    list[str],
    list[dict[str, Any]],
]
```

Add logic:
- detect brand attribute by current Ozon dictionary rule;
- try auto-match first;
- if no auto-match, try saved mapping;
- if still unresolved, append structured issue with options metadata.

Introduce narrow helper methods rather than growing `build_import_payload` further:

```python
def _resolve_saved_dictionary_value(...): ...
def _build_dictionary_issue(...): ...
def _is_brand_attribute(...): ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_mapping.py -k "dictionary_issue or saved_brand_mapping" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/mapping.py app/schemas.py tests/test_mapping.py
git commit -m "feat: expose unresolved ozon brand mapping issues"
```

## Task 3: Extend Ozon client for dictionary option retrieval and validation

**Files:**
- Modify: `app/clients/ozon.py`
- Modify: `tests/test_mapping.py` or create `tests/test_ozon_client.py`

- [ ] **Step 1: Write failing test for dictionary option lookup**

```python
async def test_get_brand_dictionary_values_filters_by_query(mock_ozon_client):
    result = await client.get_dictionary_values(..., search="удачу")
    assert result == [{"id": 111, "value": "Все на удачу"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ozon_client.py -k dictionary_values -v`
Expected: FAIL because the Ozon client has no reusable dictionary lookup method.

- [ ] **Step 3: Implement Ozon dictionary value lookup**

Add a focused client method:

```python
async def get_dictionary_values(
    self,
    credentials: dict[str, str],
    *,
    attribute_id: int,
    description_category_id: int,
    type_id: int,
    search: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    ...
```

Requirements:
- reuse existing Ozon request plumbing;
- prefer server-side search when API supports it;
- normalize output to `{"id": ..., "value": ...}`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ozon_client.py -k dictionary_values -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/clients/ozon.py tests/test_ozon_client.py
git commit -m "feat: add ozon dictionary value lookup"
```

## Task 4: Extend preview/import flow and add mappings API

**Files:**
- Modify: `app/services/transfer.py`
- Modify: `app/api/routes/transfers.py`
- Create or modify: `app/api/routes/mappings.py`
- Modify: `app/schemas.py`
- Test: `tests/test_transfers_api.py`

- [ ] **Step 1: Write failing API tests for preview issues, save mapping, and import blocking**

```python
def test_preview_returns_dictionary_issues(client):
    response = client.post("/api/v1/transfers/preview", json=payload)
    assert response.status_code == 200
    assert response.json()["dictionary_issues"][0]["type"] == "brand"


def test_save_dictionary_mapping(client):
    response = client.post("/api/v1/mappings/dictionary", json=payload)
    assert response.status_code == 200


def test_import_is_blocked_when_brand_mapping_unresolved(client):
    response = client.post("/api/v1/transfers", json=payload)
    assert response.status_code == 400
    assert "brand" in response.json()["detail"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_transfers_api.py -k "dictionary_issues or save_dictionary_mapping or brand_mapping_unresolved" -v`
Expected: FAIL because preview/import contracts and mappings API are missing.

- [ ] **Step 3: Implement backend API and preview/import integration**

Backend changes:
- extend `TransferPreviewResponse` with `dictionary_issues`;
- aggregate item-level issues into response-level data needed by UI;
- ensure `ready_to_import` becomes `False` when unresolved brand issues exist;
- add `POST /api/v1/mappings/dictionary`;
- validate selected dictionary values against Ozon before persisting;
- make import return a business error that explicitly mentions unresolved brand mappings.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_transfers_api.py -k "dictionary_issues or save_dictionary_mapping or brand_mapping_unresolved" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/transfer.py app/api/routes/transfers.py app/api/routes/mappings.py app/schemas.py tests/test_transfers_api.py
git commit -m "feat: add api flow for ozon brand mappings"
```

## Task 5: Add preview modal and searchable brand selection UI

**Files:**
- Modify: `app/static/app.js`
- Modify: `app/static/app.css`
- Test: `tests/test_ui_preview.py`

- [ ] **Step 1: Write failing UI test for brand mapping modal**

```python
def test_preview_shows_brand_mapping_button_when_dictionary_issues_exist():
    state = render_preview_with_issues(...)
    assert "Сопоставить бренды" in state.html


def test_brand_modal_filters_options_by_search():
    state = open_brand_modal(...)
    state.search("удачу")
    assert state.visible_options == ["Все на удачу"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ui_preview.py -k "brand_mapping_button or filters_options" -v`
Expected: FAIL because the preview UI has no modal or search.

- [ ] **Step 3: Implement modal, search, and save flow**

In `app/static/app.js`:
- add preview button gated by `dictionary_issues`;
- build modal state around unresolved brand issues;
- render searchable dropdown per issue row;
- debounce search input by 250-300 ms;
- submit selected mappings to `/api/v1/mappings/dictionary`;
- rerun preview on success.

In `app/static/app.css`:
- style modal layout;
- style search field and dropdown states;
- keep responsive layout for desktop/mobile.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ui_preview.py -k "brand_mapping_button or filters_options" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/static/app.js app/static/app.css tests/test_ui_preview.py
git commit -m "feat: add preview ui for ozon brand mapping"
```

## Task 6: Full verification and cleanup

**Files:**
- Review: all changed files

- [ ] **Step 1: Run targeted backend tests**

Run: `python -m pytest tests/test_db.py tests/test_mapping.py tests/test_ozon_client.py tests/test_transfers_api.py -v`
Expected: PASS

- [ ] **Step 2: Run frontend/UI tests**

Run: `python -m pytest tests/test_ui_preview.py -v`
Expected: PASS

- [ ] **Step 3: Run full project test suite**

Run: `python -m pytest`
Expected: PASS

- [ ] **Step 4: Run repository verification script**

Run: `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`
Expected: PASS

- [ ] **Step 5: Check repository state**

Run: `git status --short --branch`
Expected: only intended files changed, on the expected branch.

- [ ] **Step 6: Optional git remote verification if git config changed**

Run: `git remote -v`
Expected: `origin` points to `https://github.com/lamantinX/perenoska`
