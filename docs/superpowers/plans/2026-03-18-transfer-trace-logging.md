# Transfer Trace Logging Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-transfer trace logging with sequential internal tokens for HTTP calls and payload-formatting steps without changing transfer behavior.

**Architecture:** Introduce a small trace context that lives for one `preview` or `launch` call, persists events into a new SQLite table, and is passed into transfer, mapping, and marketplace client flows. Keep existing service boundaries and add logging only at high-value steps.

**Tech Stack:** Python, FastAPI, SQLite, pytest

---

### Task 1: Add database coverage for transfer logs

**Files:**
- Modify: `app/db.py`
- Test: `tests/test_transfer_preview.py`

- [ ] **Step 1: Write the failing test**

Add a test that creates a log row through `Database` and asserts required fields, `base_token`, and `sequence_no` are persisted.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transfer_preview.py -k transfer_log -v`
Expected: FAIL because `transfer_logs` support does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add the `transfer_logs` schema and a minimal insert/list helper in `Database`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transfer_preview.py -k transfer_log -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_transfer_preview.py app/db.py
git commit -m "feat: add transfer trace log storage"
```

### Task 2: Add trace token generation and masking helpers

**Files:**
- Modify: `app/services/transfer.py`
- Test: `tests/test_transfer_preview.py`

- [ ] **Step 1: Write the failing test**

Add tests for a trace context that generates `<base_token>_1`, `<base_token>_2`, and masks sensitive headers/body fields.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transfer_preview.py -k trace_context -v`
Expected: FAIL because helper types/functions do not exist.

- [ ] **Step 3: Write minimal implementation**

Add a focused helper in `app/services/transfer.py` for token sequencing and payload masking.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transfer_preview.py -k trace_context -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_transfer_preview.py app/services/transfer.py
git commit -m "feat: add transfer trace context helpers"
```

### Task 3: Log internal preview and launch steps

**Files:**
- Modify: `app/services/transfer.py`
- Modify: `app/services/mapping.py`
- Test: `tests/test_transfer_preview.py`

- [ ] **Step 1: Write the failing test**

Add integration-style tests proving `preview` and `launch` create function logs with sequential tokens and separate base tokens.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transfer_preview.py -k "preview_logs or launch_logs" -v`
Expected: FAIL because service logging is not wired.

- [ ] **Step 3: Write minimal implementation**

Thread the trace context through transfer and mapping service code and persist `function` events at key steps.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transfer_preview.py -k "preview_logs or launch_logs" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_transfer_preview.py app/services/transfer.py app/services/mapping.py
git commit -m "feat: log transfer formatting steps"
```

### Task 4: Log client HTTP calls and failures

**Files:**
- Modify: `app/clients/ozon.py`
- Modify: `app/clients/wb.py`
- Modify: `app/clients/yandex_market.py`
- Modify: `app/clients/base.py`
- Test: `tests/test_ozon_client.py`
- Test: `tests/test_yandex_market_client.py`

- [ ] **Step 1: Write the failing test**

Add client-focused tests that verify a successful API call and an error case both emit sanitized `http` logs.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ozon_client.py tests/test_yandex_market_client.py -k trace -v`
Expected: FAIL because clients do not emit logs yet.

- [ ] **Step 3: Write minimal implementation**

Add optional trace logging hooks to shared client request paths and use them in concrete clients.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ozon_client.py tests/test_yandex_market_client.py -k trace -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ozon_client.py tests/test_yandex_market_client.py app/clients/base.py app/clients/ozon.py app/clients/wb.py app/clients/yandex_market.py
git commit -m "feat: log marketplace http requests"
```

### Task 5: Run full verification

**Files:**
- Modify: none unless fixes are needed
- Test: `tests/test_transfer_preview.py`
- Test: `tests/test_ozon_client.py`
- Test: `tests/test_yandex_market_client.py`

- [ ] **Step 1: Run targeted tests**

Run: `python -m pytest tests/test_transfer_preview.py tests/test_ozon_client.py tests/test_yandex_market_client.py -v`
Expected: PASS

- [ ] **Step 2: Run full suite**

Run: `python -m pytest`
Expected: PASS

- [ ] **Step 3: Run project verification**

Run: `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`
Expected: PASS

- [ ] **Step 4: Inspect workspace state**

Run: `git status --short --branch`
Expected: only intended files changed

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: add transfer trace logging"
```
