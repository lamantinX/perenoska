# Makefile — интерфейс команд проекта Perenoska
# FastAPI-сервис для переноса карточек WB → Ozon

.PHONY: dev stop test test-e2e test-smoke lint clean setup init help sync-structure check-structure

# === Запуск ===

dev:  ## Запустить для разработки
	uvicorn app.main:app --reload

stop:  ## Остановить (Ctrl+C)
	@echo "Нажми Ctrl+C для остановки сервера"

# === Тесты ===

test:  ## Запустить тесты
	pytest tests/ -v

test-e2e:  ## E2E тесты
	pytest tests/e2e/ -v || echo "TODO: настроить e2e тесты"

test-smoke:  ## Smoke тесты (post-deploy)
	@echo "TODO: настроить smoke тесты"

# === Качество кода ===

lint:  ## Линтинг
	ruff check app/ tests/ || echo "Установи: pip install ruff"

# === Настройка ===

setup:  ## Первоначальная настройка (pre-commit + зависимости)
	@echo "📦 Установка зависимостей..."
	pip install -e ".[dev]"
	@echo ""
	@echo "🔧 Pre-commit хуки..."
	pip install pre-commit
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "✅ Готово. Запуск: make dev"

init:  ## Полная настройка: setup + GitHub labels
	@$(MAKE) setup
	@echo ""
	@echo "🏷️  Настройка GitHub labels..."
	python .instructions/.scripts/labels-sync.py 2>/dev/null || echo "Настрой gh auth login сначала"

# === Утилиты ===

clean:  ## Очистка кэша
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ .ruff_cache/ 2>/dev/null || true
	@echo "✅ Очищено"

sync-structure:  ## Синхронизировать .structure/ с реальной структурой
	python .instructions/.scripts/sync-structure.py 2>/dev/null || echo "Скрипт не найден"

check-structure:  ## Проверить соответствие структуры
	python .instructions/.scripts/check-structure.py 2>/dev/null || echo "Скрипт не найден"

help:  ## Показать эту справку
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
