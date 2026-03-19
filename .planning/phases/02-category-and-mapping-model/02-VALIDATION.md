---
phase: 2
slug: category-and-mapping-model
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-18
---

# Phase 2 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/test_yandex_market_client.py tests/test_dictionary_mappings.py` |
| **Mapping regression command** | `python -m pytest tests/test_transfer_preview.py -k mapping` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After metadata tasks:** Run `python -m pytest tests/test_yandex_market_client.py`
- **After mapping-persistence tasks:** Run `python -m pytest tests/test_dictionary_mappings.py tests/test_transfer_preview.py -k mapping`
- **After every plan wave:** Run `python -m pytest`
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | CAT-03 | client | `python -m pytest tests/test_yandex_market_client.py -k categories` | yes | pending |
| 2-01-02 | 01 | 1 | CAT-04 | client | `python -m pytest tests/test_yandex_market_client.py -k attributes` | yes | pending |
| 2-02-01 | 02 | 2 | MAP-01 | service | `python -m pytest tests/test_transfer_preview.py -k category` | yes | pending |
| 2-02-02 | 02 | 2 | MAP-02 | api | `python -m pytest tests/test_dictionary_mappings.py tests/test_transfer_preview.py -k mapping` | yes | pending |
| 2-02-03 | 02 | 2 | MAP-03 | api | `python -m pytest tests/test_dictionary_mappings.py tests/test_transfer_preview.py -k dictionary` | yes | pending |
| 2-03-01 | 03 | 3 | MAP-02 | integration | `python -m pytest tests/test_transfer_preview.py -k category` | yes | pending |
| 2-03-02 | 03 | 3 | MAP-03 | integration | `python -m pytest` | yes | pending |

---

## Wave 0 Requirements

Existing infrastructure already covers database, API, and preview-path regression. No extra wave 0 work is required before planning execution.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Yandex Market appears in current mapping dialogs without broken selector or save behavior | MAP-02, MAP-03 | No browser automation exists in repo | Open `/`, generate a preview scenario that surfaces category or controlled-value issues involving Yandex Market, save a mapping, rerun preview, and confirm the issue is resolved or reduced |

---

## Validation Sign-Off

- [x] All planned task families map to automated verification
- [x] Sampling continuity is preserved across waves
- [x] No watch-mode or manual-only gates block execution
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
