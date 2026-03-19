# AGENTS.md

Локальные инструкции для Codex в репозитории `perenoska`.

## Контекст

- Проект: FastAPI MVP для переноса карточек товаров между Wildberries и Ozon.
- Репозиторий локально привязан к форку: `https://github.com/lamantinX/perenoska`
- Backend, API, сервисы и SQLite-слой находятся в `app/`.
- Встроенный frontend лежит в `app/static/`.
- Тесты находятся в `tests/`.

## Базовые команды

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
Copy-Item .env.example .env
uvicorn app.main:app --reload
python -m pytest
powershell -ExecutionPolicy Bypass -File scripts/verify.ps1
```

## Что читать сначала

1. `README.md`
2. `docs/codex/project-overview.md`
3. `docs/codex/file-map.md`
4. `docs/codex/workflow.md`

## Правила работы в этом проекте

- Не менять продуктовую логику без явного запроса.
- Для изменений поведения сначала добавлять или обновлять тест.
- Для документационных и инфраструктурных правок не раздувать репозиторий лишними файлами.
- Сохранять UTF-8 и читаемые русскоязычные тексты.
- Не трогать SQLite-файл базы вручную; менять только код, конфиг или `.env`.
- При правках API или сервисов смотреть связанные тесты в `tests/`.
- Если меняется маршрут, проверять `app/static/app.js` на соответствие frontend-ожиданиям.

## Осторожные зоны

- `app/db.py` — схема SQLite и доступ к данным;
- `app/services/transfer.py` — ключевая логика preview/import;
- `app/services/mapping.py` — эвристики сопоставления;
- `app/static/app.js` — весь встроенный UI;
- `app/clients/wb.py` и `app/clients/ozon.py` — интеграционные адаптеры.

## Ожидаемая проверка перед завершением

- перечитать изменённые документы и служебные файлы;
- запустить `python -m pytest`;
- запустить `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`;
- проверить `git status --short --branch`;
- убедиться, что `git remote -v` указывает на `lamantinX/perenoska`, если работа касается git-настройки.
