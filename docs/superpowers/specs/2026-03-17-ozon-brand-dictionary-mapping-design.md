# Ozon Brand Dictionary Mapping Design

**Date:** 2026-03-17

## Goal

Добавить в `preview/import` управляемый сценарий ручного сопоставления брендов для Ozon, если автоматический dictionary match не найден. Сопоставления должны сохраняться как постоянные правила для конкретной пары кабинетов и повторно использоваться в следующих переносах.

## Scope

В `v1` входит:

- только сценарий `brand`;
- привязка правил к конкретной паре подключений `source_connection_id` + `target_connection_id`;
- расширение `preview` структурированными unresolved dictionary issues;
- кнопка открытия модального окна из preview, если есть несопоставленные бренды;
- блокировка `import`, если brand issues не были сопоставлены автоматически или вручную;
- поиск по списку брендов Ozon в модальном окне;
- переиспользуемый каркас backend-модели и API под будущие dictionary-кейсы.

В `v1` не входит:

- ручное сопоставление категорий;
- ручное сопоставление других атрибутов Ozon;
- отдельный экран администрирования mappings вне preview;
- глобальные mappings между всеми кабинетами.

## Current Project Snapshot

Сейчас логика подготовки payload для Ozon живет в `app/services/mapping.py`. При отсутствии dictionary match сервис добавляет warning вида `Ozon dictionary match not found for "Бренд": ...`, но не предоставляет пользователю способ вручную выбрать допустимое значение и сохранить правило.

Frontend находится в `app/static/app.js` и уже умеет показывать preview-результат и warnings. Это дает естественную точку входа для кнопки открытия модалки и повторного пересчета preview после сохранения соответствий.

## Proposed Approach

### 1. Persistent dictionary mappings in SQLite

Добавить новую таблицу `dictionary_mappings` в `app/db.py` для хранения ручных правил сопоставления. Каждое правило должно быть уникально для комбинации:

- `source_connection_id`
- `target_connection_id`
- `mapping_type`
- `source_value_normalized`

Минимальный состав полей:

- `id`
- `source_connection_id`
- `target_connection_id`
- `mapping_type`
- `source_value_raw`
- `source_value_normalized`
- `target_attribute_id`
- `target_dictionary_value_id`
- `target_dictionary_value`
- `created_at`
- `updated_at`

`source_value_normalized` нужен, чтобы избежать дублей из-за регистра и пробелов.

### 2. Preview returns structured unresolved issues

`MappingService` должен использовать такой порядок разрешения бренда:

1. попытка текущего автоматического dictionary match;
2. lookup в сохраненных ручных mappings;
3. если совпадение не найдено, формирование unresolved issue.

В ответ `preview` нужно добавить структурированный блок:

```json
{
  "dictionary_issues": [
    {
      "type": "brand",
      "source_value": "Все на удачу",
      "source_value_normalized": "все на удачу",
      "target_attribute_id": 123,
      "target_attribute_name": "Бренд",
      "options": [
        { "id": 111, "value": "Все на удачу" },
        { "id": 112, "value": "Все для удачи" }
      ]
    }
  ]
}
```

Текущий текстовый warning можно сохранить для обратной совместимости UI, но источником правды для нового поведения должен стать `dictionary_issues`.

### 3. Save mappings through dedicated API

Добавить endpoint, условно `POST /api/v1/mappings/dictionary`, который принимает пакет ручных соответствий и сохраняет их как постоянные правила для пары кабинетов.

Пример payload:

```json
{
  "source_connection_id": 1,
  "target_connection_id": 2,
  "items": [
    {
      "type": "brand",
      "source_value": "Все на удачу",
      "target_attribute_id": 123,
      "target_dictionary_value_id": 111,
      "target_dictionary_value": "Все на удачу"
    }
  ]
}
```

Поведение endpoint:

- обновляет существующее правило, если оно уже есть;
- валидирует, что выбранный `target_dictionary_value_id` допустим для данного Ozon-атрибута;
- возвращает нормализованный результат сохранения;
- не сохраняет несогласованные значения.

### 4. Import blocks on unresolved brand issues

Если на этапе `import` для товара остались unresolved `brand` dictionary issues, импорт должен быть остановлен понятной бизнес-ошибкой. Silent fallback в `Нет бренда` или пропуск поля в `v1` не допускаются, потому что это меняет продуктовые данные и может приводить к ошибкам модерации Ozon.

### 5. Searchable brand mapping modal in UI

В `app/static/app.js` нужно добавить:

- кнопку `Сопоставить бренды` в preview, если есть `dictionary_issues` с `type=brand`;
- модальное окно со строками сопоставления;
- для каждой строки:
  - слева исходный бренд WB;
  - справа searchable dropdown со значениями брендов Ozon;
- повторный вызов preview после успешного сохранения mappings;
- повторное использование этой же модалки, если пользователь нажал import и получил блокировку из-за unresolved mappings.

### 6. Search behavior

`v1` должен поддерживать поиск по брендам Ozon:

- поиск без учета регистра;
- debounce 250-300 ms;
- отображение состояния `Ничего не найдено`;
- предпочтителен серверный поиск через Ozon API, если клиент Ozon умеет искать dictionary values по query;
- если API не поддерживает поиск и объем значений разумный, допустима локальная фильтрация уже загруженного списка.

## File Plan

### Files to modify

- `app/db.py`
- `app/services/mapping.py`
- `app/services/transfer.py`
- `app/clients/ozon.py`
- `app/api/routes/...` для нового endpoint mappings и/или расширения preview/import контрактов
- `app/static/app.js`
- связанные схемы/модели ответов, если они вынесены отдельно
- `tests/...` для db, api, mapping и frontend/UI-логики

### Possible new files

- новый route/module для dictionary mappings, если текущие routes логично не расширять;
- новый service/repository для persistent mappings, если это уменьшит сложность `mapping.py`;
- новые тестовые файлы под API и service сценарии.

## Data and Error Handling

- Mapping применяется только если совпадают оба подключения: источник и целевой кабинет.
- Если сохраненное значение больше не существует в словаре Ozon, правило считается устаревшим и preview снова формирует unresolved issue.
- Если один и тот же бренд встречается в нескольких товарах preview, UI должен требовать выбрать соответствие один раз и затем применять его ко всем совпадениям после пересчета.
- Ошибки валидации сохранения mappings должны быть отдельными от ошибок preview/import.

## Testing Strategy

Минимальный набор проверок:

- unit-тест на lookup сохраненного mapping;
- unit-тест на формирование `dictionary_issues`, когда auto-match не найден;
- unit-тест на блокировку import без mapping;
- API-тест на сохранение mappings;
- API-тест на update существующего mapping;
- API-тест на preview после сохранения mapping;
- UI-тест на видимость кнопки модалки;
- UI-тест на поиск по списку брендов;
- UI-тест на повторный preview после сохранения.

## Risks

- Ozon API для dictionary values может иметь ограничения по поиску, пагинации или размеру ответа;
- если список брендов слишком большой, локальная фильтрация может быть неудобной и тяжелой;
- расширение preview/import контрактов потребует аккуратного обновления встроенного UI, чтобы не сломать текущий сценарий.

## Success Criteria

- Preview явно показывает несопоставленные бренды через структурированные issues.
- Пользователь может открыть модалку, найти бренд Ozon через поиск, выбрать значение и сохранить соответствие.
- Сопоставление сохраняется как постоянное правило для конкретной пары кабинетов.
- Повторный preview больше не показывает resolved brand issue.
- Import блокируется, только если unresolved brand issues все еще существуют.
