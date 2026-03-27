---
description: Ревью кода для 0002-wb-ozon-product-transfer.
standard: specs/.instructions/analysis/review/standard-review.md
standard-version: v1.2
parent: specs/analysis/0002-wb-ozon-product-transfer/plan-dev.md
index: specs/analysis/README.md
milestone: v1.0.0
status: OPEN
---

# review: 0002 Wb ozon product transfer

**Ветка:** 0002-wb-ozon-product-transfer
**Base:** main

## Контекст ревью

> Секция заполняется при /review-create (до начала разработки).
> Содержит все ссылки, необходимые code-reviewer при запуске /review.

### Постановка

| Документ | Путь |
|----------|------|
| Discussion | `specs/analysis/0002-wb-ozon-product-transfer/discussion.md` |
| Design | `specs/analysis/0002-wb-ozon-product-transfer/design.md` |
| Plan Tests | `specs/analysis/0002-wb-ozon-product-transfer/plan-test.md` |
| Plan Dev | `specs/analysis/0002-wb-ozon-product-transfer/plan-dev.md` |

### perenoska (critical-medium)

| Секция | Путь | Что проверяем |
|--------|------|----------------|
| § 1 Назначение и критичность | `specs/docs/perenoska.md#назначение-и-критичность` | Planned Changes |
| § 2 API контракты | `specs/docs/perenoska.md#api-контракты` | MODIFIED: preview (brand_id/category_confidence/requires_manual), transfer (product_overrides+attributes), ADDED: GET /api/v1/catalog/{marketplace}/brands |
| § 4 Потоки данных | `specs/docs/perenoska.md#потоки-данных` | MODIFIED: preview WB→Ozon (LLM маппинг категорий, поиск brand_id), launch (product_overrides блокировка) |
| § 5 Code Map | `specs/docs/perenoska.md#code-map` | MODIFIED: mapping.py (auto_match_category_llm, find_brand_id, build_import_payload), ozon.py (list_brands), schemas.py, catalog.py |
| § 6 Зависимости | `specs/docs/perenoska.md#зависимости` | ADDED: openai SDK (AsyncOpenAI, OpenRouter) |
| § 8 Границы автономии LLM | `specs/docs/perenoska.md#границы-автономии-llm` | Что можно без флага, что требует CONFLICT |
| § 9 Planned Changes | `specs/docs/perenoska.md#planned-changes` | **Эталон для P1-сверки** |

*Незатронутые секции не включаются.*

### Системная документация

- `specs/docs/.system/overview.md`
- `specs/docs/.system/conventions.md`
- `specs/docs/.system/testing.md`
- `specs/docs/.system/infrastructure.md`

### Tech-стандарты

| Технология | Стандарт |
|------------|----------|
| fastapi | `specs/docs/.technologies/standard-fastapi.md` |
| python | `specs/docs/.technologies/standard-python.md` |
| rest | `specs/docs/.technologies/standard-rest.md` |

### Процесс разработки

- [validation-development.md](/.github/.instructions/development/validation-development.md)
