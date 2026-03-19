# Concerns

## Highest-risk areas

### `app/services/transfer.py`

- This is the orchestration hub for preview, import launch, status sync, saved mapping lookup, category issue grouping, dictionary option hydration, and product overrides.
- The file mixes coordination, policy, payload assembly, DB access, and remote enrichment concerns.
- Behavioral changes here can easily regress preview readiness, mapping recovery, or import execution.

### `app/services/mapping.py`

- Contains marketplace-specific heuristics, normalization, synonym tables, payload shaping, critical field detection, and Ozon/WB divergence.
- Several helpers encode business rules implicitly in string matching and hard-coded attribute IDs (for example Ozon brand/dictionary behavior).
- Small edits can create subtle false positives/negatives in mapping and readiness logic.

### `app/db.py`

- Schema and all persistence logic are centralized in one file.
- There is no migration framework, so schema evolution must be done manually in code.
- Both legacy-looking and generalized mapping tables exist, which raises maintenance and data consistency questions.

## Security concerns

- `app/config.py` falls back to `unsafe-local-development-secret`; if reused outside local dev, encrypted credentials and sessions become weakly protected.
- Sessions are persisted in SQLite without visible cleanup/rotation logic.
- No explicit CSRF or rate-limiting layer was found; acceptable for token API usage, but relevant if the SPA usage expands.
- Secret scanning/commit hooks are not evident in the repo tooling.

## Reliability concerns

- No background worker or queue: imports run inline from API-triggered flows.
- `TransferService.launch()` does remote API work synchronously in request context after creating the job row.
- Retry logic, backoff, circuit breaking, and rate limiting are not present in inspected integration code.
- SQLite is convenient for MVP use but constrains write concurrency and operational robustness.

## Integration fragility

- WB parsing relies on multiple response shapes and auxiliary public endpoints; upstream drift can silently degrade enrichment.
- Ozon category/type resolution uses heuristics against source product text and attributes; category trees may change.
- Some Ozon endpoints are optional in practice and degrade to partial data, which is resilient but can hide integration drift.

## Architectural debt

- Mapping persistence now appears generalized in `mappings`, but `dictionary_mappings` table remains in schema.
- `TransferService` reaches into underscore-prefixed helpers on `MappingService`, which signals missing public abstractions.
- The frontend is entirely concentrated in one `app/static/app.js` file; scaling UI complexity will be harder without modularization.
- There is no dedicated migration/versioning story for DB schema or API contracts.

## Testing and quality concerns

- There is good scenario coverage, but no frontend automation was found.
- No lint/typecheck/test matrix is declared beyond pytest.
- `scripts/verify.ps1` currently runs pytest and `git remote -v`; it does not enforce formatting, types, or static analysis.

## Operational concerns

- Python `>=3.14` is aggressive and may narrow deploy/runtime options.
- Repository currently has a dirty worktree with many modified and untracked files; this increases risk of mixing mapping artifacts with unrelated changes.
- `.planning/codebase/` is generated documentation and may need explicit workflow discipline to stay fresh after code changes.

## Recommended watchpoints for future work

- Treat `app/services/transfer.py`, `app/services/mapping.py`, `app/db.py`, and `app/static/app.js` as mandatory review points.
- Before refactors, clarify whether `dictionary_mappings` should be removed or kept for backward compatibility.
- If imports become heavier, move launch/sync work behind a queue or background task system.
