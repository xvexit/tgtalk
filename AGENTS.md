# AGENTS.md

Проект: Telegram-бот, который отвечает от имени владельца аккаунта через Telegram Business API
(Автоматизация чатов). Подробности: `docs/architecture.md`. План: `docs/roadmap.md`. Решения: `docs/decisions.md`.

## Главные правила

1. **Не принимай архитектурных решений сам.** Если задаче нужно решение, которого нет в `docs/`
   (новая зависимость, новая таблица, изменение контракта, смена границ модулей) — остановись и спроси.
2. **Работай только в рамках текущего этапа** из `docs/roadmap.md`. Пункты «вне рамок» не делай, даже если «заодно удобно».
3. **Не объявляй этап готовым, пока не прошёл его критерий готовности** (команда из roadmap). Покажи вывод команды.
4. Сначала план, потом код. Для каждого этапа предложи план и дождись одобрения.
5. Одна задача = один небольшой коммит с понятным сообщением. Не смешивай рефакторинг и фичи.

## Безопасность (нарушение недопустимо)

- Реальные сообщения никогда не отправляются в тестах и в CI. Отправка идёт только через `Sender`, в тестах там заглушка.
- Отправка в Telegram включена только при `SEND_ENABLED=true`. По умолчанию `false` (dry-run: только лог).
- Не читай, не изменяй и не печатай `.env`. Не логируй токены, ключи и полные тексты переписок на уровне INFO.
- Не коммить `.env`, `data/`, экспорты переписок, дампы БД.
- Ответы бота не должны раскрывать, что это бот (правило персоны), но код не должен обходить `guards`.

## Стек

Python 3.12, aiogram 3, PostgreSQL 16 + pgvector, SQLAlchemy 2 (async) + asyncpg + Alembic,
pydantic v2 / pydantic-settings, OpenAI-совместимый клиент (`openai` SDK) для DeepSeek,
pytest + pytest-asyncio, ruff, mypy (strict для `core/`). Запуск: Docker Compose.

## Структура

```
src/tgtwin/
  core/        # модели, контракты (Protocol), Pipeline. Не импортирует aiogram, SQLAlchemy, openai.
  steps/       # шаги пайплайна, по одному классу на файл-тему. Регистрация в steps/registry.py
  adapters/    # telegram/ (aiogram -> IncomingMessage, Sender). Единственное место, где знают о Telegram.
  llm/         # реализации LLMProvider (openai_compat.py, fake.py)
  storage/     # db.py, models.py (ORM), repositories.py, migrations/ (alembic)
  ingestion/   # парсер экспорта Telegram, нарезка на диалоги
  eval/        # оценочный стенд
  app.py       # сборка зависимостей (composition root)
tests/
docs/
```

Правило зависимостей: `core` ни от чего не зависит; `steps` зависят от `core` и интерфейсов;
реализации (`adapters`, `llm`, `storage`) подключаются только в `app.py`.

## Команды

```
docker compose up -d --build        # запустить всё
docker compose logs -f bot          # логи бота
docker compose run --rm bot pytest  # тесты
docker compose run --rm bot ruff check . && docker compose run --rm bot mypy src/tgtwin/core
docker compose run --rm bot alembic upgrade head
docker compose run --rm bot alembic revision --autogenerate -m "msg"
```

## Стиль кода

- Типы везде, `from __future__ import annotations`. Pydantic на границах (конфиги, внешние данные).
- Асинхронный код не блокирует цикл (никаких sync-запросов к БД/сети внутри async).
- Новая фича = новый `Step` + строка в `registry.py` + тест. Не правь `Pipeline` ради фичи.
- Каждый шаг покрыт юнит-тестом на заглушках, без сети и без Telegram.
- Логи: структурные, с `chat_id` и `message_id`, без текста сообщений на INFO.
