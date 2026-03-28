---
description: Ревью кода для 0002-wb-ozon-product-transfer.
standard: specs/.instructions/analysis/review/standard-review.md
standard-version: v1.2
parent: specs/analysis/0002-wb-ozon-product-transfer/plan-dev.md
index: specs/analysis/README.md
milestone: v1.0.0
status: RESOLVED
review-iteration: 3
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

---

## Итерация 1

**Дата:** 2026-03-26
**Ветка:** 0002-wb-ozon-product-transfer
**Коммиты:** 9e94aab..HEAD (12 коммитов разработки)

### perenoska

**RV-1 [P2] `app/services/transfer.py:277-305` — мёртвый цикл и избыточные проверки в `launch()`**
В строках 277-281 присутствует цикл `for product_id in payload.product_ids: ... pass` — явный мёртвый код. Проверки `category_requires_manual and override_category_id is None` на строках 290, 298 логически недостижимы: если override передан, `preview()` уже обнулит флаг. Реальная блокировка работает через `not preview.ready_to_import` на строке 307.
Статус: OPEN

**RV-2 [P2] `app/services/transfer.py:142-156` — блокировка при пустых images через побочный эффект**
При `product.images == []` код добавляет предупреждение и делает `continue`, создавая item без `target_category_id`. Блокировка переноса достигается косвенно (через `item.target_category_id is None`), а не явным флагом. REQ-4 требует явной блокировки при отсутствии изображений. Если overrides предоставят `category_id`, логика сломается.
Статус: OPEN

**RV-3 [P2] `app/services/mapping.py:63-64` + `transfer.py:64` — LLM получает все категории (включая родительские), а не только leaf**
`target_categories_dicts` строится из всего flatten-дерева Ozon. Design.md § 9 требует передавать "до 50 leaf-категорий". Родительские категории (без `type_id`) не подходят для создания карточки.
Статус: OPEN

**RV-4 [P2] `app/services/mapping.py:109` — `find_brand_id()` не перехватывает не-`MarketplaceAPIError` исключения от `ozon_client.list_brands()`**
Если httpx не оборачивает все ошибки в `MarketplaceAPIError`, получим 500 вместо 502. Нужно проверить `OzonClient._request()` и подтвердить что все сетевые исключения оборачиваются корректно.
Статус: OPEN

**RV-5 [P3] `app/schemas.py:128` — `attributes: list | None = None` без generic-типизации; overrides.attributes не применяются в `_apply_product_overrides()`**
`list` без `[dict[str, Any]]` нарушает стандарт Pydantic. Поле `attributes` в override не обрабатывается в `transfer.py:237-247`.
Статус: OPEN

**RV-6 [P3] `tests/test_mapping_payload.py` — отсутствие явного комментария о семантике `ProductDetails.description` как `annotation` для Ozon**
Тесты корректны, но `description` для Ozon-карточек семантически является `annotation` — это нигде явно не задокументировано в модели.
Статус: OPEN

**RV-7 [P3] `app/services/mapping.py:401-407` — дублированная/мёртвая проверка в `_sanitize_offer_id()`**
Вторая проверка `cleaned[:3].startswith("_") or cleaned[:3].startswith("-")` никогда не срабатывает после первой (строка 403).
Статус: OPEN

**RV-8 [P3] `tests/test_transfer_service_integration.py:478-502` — TC-37 использует `CountingOzonClient` вместо `mocker.spy()` как требует plan-test.md**
Функционально корректно, но расходится с постановкой.
Статус: OPEN

### Итого

| Сервис | P1 | P2 | P3 | Open | Resolved |
|--------|----|----|-----|------|----------|
| perenoska | 0 | 4 | 4 | 8 | 0 |
| **Итого** | **0** | **4** | **4** | **8** | **0** |

**Вердикт:** NOT READY

---

## Итерация 2

**Дата:** 2026-03-26
**Fix-итерация:** RV-1..RV-8 исправлены

### perenoska

RV-1: RESOLVED — мёртвый код в launch() удалён
RV-2: RESOLVED — явный missing_critical_fields=["images"] при пустых images
RV-3: RESOLVED — leaf-фильтрация для LLM категорий
RV-4: RESOLVED — обработка исключений в find_brand_id()
RV-5: RESOLVED — типизация list[dict[str, Any]]
RV-6: RESOLVED — комментарий description→annotation
RV-7: RESOLVED — мёртвая проверка удалена
RV-8: RESOLVED — mocker.spy() вместо CountingOzonClient

**RV-9 [P2] `app/services/transfer.py:launch()` — непрозрачное сообщение при missing_critical_fields**
launch() не указывал конкретный product_id и поля при блокировке через missing_critical_fields.
Статус: OPEN

### Итого

| Сервис | P1 | P2 | P3 | Open | Resolved |
|--------|----|----|-----|------|----------|
| perenoska | 0 | 1 | 0 | 1 | 8 |
| **Итого** | **0** | **1** | **0** | **1** | **8** |

**Вердикт:** NOT READY

---

## Итерация 3

**Дата:** 2026-03-26
**Fix-итерация:** RV-9 исправлен

### perenoska

RV-9: RESOLVED — per-item проверка missing_critical_fields с actionable-сообщением в launch()

### Итого

| Сервис | P1 | P2 | P3 | Open | Resolved |
|--------|----|----|-----|------|----------|
| perenoska | 0 | 0 | 0 | 0 | 9 |
| **Итого** | **0** | **0** | **0** | **0** | **9** |

**Вердикт:** READY
