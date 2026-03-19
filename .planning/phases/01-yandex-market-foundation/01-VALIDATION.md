---
phase: 1
slug: yandex-market-foundation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-18
---

# Phase 1 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/test_auth_and_connections.py tests/test_yandex_market_client.py` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_auth_and_connections.py tests/test_yandex_market_client.py`
- **After every plan wave:** Run `python -m pytest`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | CONN-01 | api | `python -m pytest tests/test_auth_and_connections.py -k yandex_market_connection` | ✅ | ⬜ pending |
| 1-01-02 | 01 | 1 | CONN-02 | api | `python -m pytest tests/test_auth_and_connections.py -k yandex_market_connection` | ✅ | ⬜ pending |
| 1-02-01 | 02 | 1 | CAT-01 | client | `python -m pytest tests/test_yandex_market_client.py -k list_products` | ✅ | ⬜ pending |
| 1-02-02 | 02 | 1 | CAT-02 | client | `python -m pytest tests/test_yandex_market_client.py -k product_details` | ✅ | ⬜ pending |
| 1-02-03 | 02 | 1 | CAT-02 | api | `python -m pytest tests/test_auth_and_connections.py -k yandex_market_catalog` | ✅ | ⬜ pending |
| 1-03-01 | 03 | 2 | UI-01 | integration | `python -m pytest tests/test_auth_and_connections.py tests/test_yandex_market_client.py` | ✅ | ⬜ pending |
| 1-03-02 | 03 | 2 | UI-02 | integration | `python -m pytest tests/test_auth_and_connections.py tests/test_yandex_market_client.py` | ✅ | ⬜ pending |
| 1-03-03 | 03 | 2 | CAT-01 | regression | `python -m pytest` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Yandex Market connection form appears and can be submitted from the embedded UI | UI-02 | No frontend automation currently exists in repo | Open `/`, log in, verify Yandex Market form is visible beside other marketplace connection forms and accepts token/business/campaign inputs |
| Yandex Market appears in selectors and source catalog workflow | UI-01 | Current UI is manual SPA without browser test coverage | Open `/`, verify Yandex Market is selectable as source/target marketplace and source catalog loading path is visible |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
