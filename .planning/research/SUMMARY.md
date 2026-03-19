# Research Summary

## Domain

Extend the existing WB/Ozon transfer MVP so Yandex Market becomes a third first-class marketplace with near-parity workflow support.

## Key findings

### Stack

- The current architecture is sufficient; no platform rewrite is needed.
- Yandex Market should be integrated as a dedicated marketplace client plus schema/service/mapping/UI extensions.
- The credentials model must likely carry more context than a single token because Market APIs are business/campaign oriented.

### Table stakes

- Connection management
- Catalog/category/attribute reads
- Preview in both directions
- Manual and automatic mapping support
- Import launch and status sync
- Built-in UI support across the existing workflow

### Architecture

- `app/clients/` gains a Market adapter
- `app/schemas.py` gains a third marketplace and Market-specific connection/context fields
- `app/services/mapping.py` and `app/services/transfer.py` are the main implementation centers
- Existing generalized mapping storage should be reused

### Watch-outs

- Category/parameter support is the hardest part
- Do not model Market as a token-only integration
- Do not stop at source-only support if the stated goal is full-cycle parity
- Keep backend/UI contracts synchronized

## Recommended planning posture

- Plan the work as a brownfield expansion, not a greenfield feature spike
- Keep requirements symmetric around source and target directions involving Yandex Market
- Separate “connection/catalog plumbing” from “preview/mapping/import parity” in the roadmap

## Sources

- Official Yandex Market developer docs inspected on 2026-03-17
- https://yandex.ru/dev/market/partner-api/
