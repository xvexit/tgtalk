# Архитектура

## Цель

Бот-секретарь: принимает `business_message` из личных чатов владельца и отвечает от его имени в его стиле.
Стиль достигается не файнтюном, а связкой: профиль стиля + похожие примеры из прошлых переписок (RAG) + недавний контекст.
Поведение по контактам и группам настраивается данными (БД), а не кодом.

## Принципы

1. **Ядро не знает о конкретных фичах.** Всё поведение = цепочка шагов `Step`.
2. **Ядро не знает о Telegram, БД и LLM.** Только интерфейсы (Protocol).
3. **Поведение описывается конфигом.** Приоритет: контакт > группа > дефолт.
4. **Безопасность по умолчанию.** Отправка выключена (`SEND_ENABLED=false`), любая неопределённость = молчать или эскалировать.
5. **Всё объяснимо.** Для каждого ответа сохраняется, какой контекст и какие примеры использовались.

## Поток обработки

```
Telegram ──► Adapter ──► IncomingMessage ──► Pipeline(steps) ──► Context.reply ──► Sender ──► Telegram
                                                 │
                    resolve_config ► record ► guards ► build_context ► llm ► postprocess
```

Шаги по умолчанию (порядок задаётся конфигом, может отличаться для контакта/группы):

| Шаг | Что делает |
|---|---|
| `resolve_config` | Загружает эффективные настройки контакта (контакт > группа > дефолт) в `ctx.cfg` |
| `record` | Сохраняет входящее в `messages`. Игнорирует эхо сообщений самого бота |
| `guard_mode` | Стоп, если `mode=off` |
| `guard_owner` | Стоп для сообщений самого владельца (они только записываются) |
| `guard_takeover` | Стоп, если владелец писал в чат менее `takeover_hours` назад |
| `guard_content` | Стоп/эскалация для неподдерживаемого контента (медиа, на старте) |
| `guard_schedule` | Расписание ответов (позже) |
| `build_context` | История чата, профиль стиля, персона, RAG-примеры |
| `llm` | Генерация через `LLMProvider`. Токен `[ESCALATE]` => эскалация |
| `postprocess` | Чистка текста, задержка по длине, лимиты частоты |
| `log_reply` | Запись в `reply_log` (контекст, примеры, итог) |

## Контракты (core/)

```python
@dataclass
class IncomingMessage:
    channel: str            # "telegram"
    connection_id: str
    chat_id: int
    message_id: int
    text: str | None
    from_owner: bool
    ts: datetime

@dataclass
class Context:
    msg: IncomingMessage
    cfg: ResolvedConfig | None
    history: list[HistoryItem]
    examples: list[Example]
    system: str
    reply: str | None
    action: Action          # NONE | REPLY | ESCALATE | DRAFT
    stop: bool
    meta: dict

class Step(Protocol):
    async def handle(self, ctx: Context) -> None: ...

class LLMProvider(Protocol):
    async def generate(self, system: str, messages: list[ChatMessage]) -> str: ...

class Sender(Protocol):            # реализация: Telegram; в тестах и dry-run: заглушка
    async def send(self, msg: IncomingMessage, text: str, delay: float) -> int | None: ...
    async def notify_owner(self, connection_id: str, text: str) -> None: ...


class MessageRepository(Protocol):   # реализация: storage/repositories.py (Postgres); в тестах: in-memory
    async def add(self, msg: StoredMessage) -> None: ...
    async def exists(self, chat_id: int, message_id: int) -> bool: ...
    async def last(self, chat_id: int, n: int) -> list[HistoryItem]: ...
    async def last_owner_ts(self, chat_id: int) -> datetime | None: ...


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

Шаги получают зависимости через конструктор. Новый шаг = класс + регистрация в `steps/registry.py`.

## Режимы (`mode`)

- `off` — не отвечать вообще.
- `dry_run` — всё считается и пишется в `reply_log`, но не отправляется.
- `draft` — ответ уходит владельцу в личку с кнопками (позже).
- `auto` — отправляется сам.

Глобальный `SEND_ENABLED=false` принудительно превращает `auto` в `dry_run`.

## Конфигурация поведения

Таблицы `groups` и `contacts` хранят `mode`, `persona_id`, `overrides` (jsonb: расписание, takeover_hours, свой список шагов, rag_scope и т.д.).
`resolve_config` сливает: defaults < group < contact и возвращает типизированный `ResolvedConfig` (pydantic).
Добавление правила «с контактом X общаться иначе» = строка в БД, не изменение кода.

## Данные (PostgreSQL 16 + pgvector)

| Таблица | Поля (основные) |
|---|---|
| `messages` | id, chat_id, tg_message_id, role (`them`/`owner`/`bot`), text, ts, connection_id, source (`live`/`import`), UNIQUE(chat_id, tg_message_id) |
| `groups` | id, name, mode, persona_id, overrides jsonb |
| `contacts` | chat_id PK, display_name, group_id, mode, persona_id, overrides jsonb |
| `personas` | id, name, system_prompt |
| `style_profiles` | id, scope (`global`/`chat:<id>`), text, built_at |
| `chunks` | id, chat_id, text, started_at, embedding vector(N) — этап RAG, размерность зависит от модели |
| `reply_log` | id, chat_id, trigger_message_id, mode, reply, context jsonb, sent bool, ts |
| `imports` | id, file_hash, filename, chats jsonb, stats jsonb, imported_at, UNIQUE(file_hash, chats) — идемпотентность загрузки экспорта |

Схема меняется только миграциями Alembic.

## Ingestion

Парсер `result.json` из Telegram Desktop: `text` бывает строкой или списком фрагментов; сервисные сообщения,
пересылки и сообщения без текста пропускаются. Поддержаны полный экспорт (`personal_chats.list`/`chats.list`) и
экспорт одного чата (корневой `messages`). Владелец определяется по `personal_information.user_id`, иначе по
`--owner-id`; роли `owner`/`them` — по `from_id`.
В каждом чате импортируются только сообщения старше самого раннего `source='live'`; импортированные получают
`source='import'`. Загрузка идемпотентна (хэш файла + набор выбранных чатов + UNIQUE по сообщению).
`list` по умолчанию сортирует по числу сообщений владельца и показывает 40 строк; доступны `--sort mine|total|last`,
`--min-mine`, `--limit`; имена чатов выводятся только с `--names`.
Нарезка на «диалоги» по паузе (например, 6 часов) — этап 4.

## Оценка качества

Часть переписок откладывается (последние N% по времени). Стенд берёт реплики собеседника, генерирует ответ без доступа
к отложенному, сравнивает с реальным ответом владельца (метрики: длина, словарь, эмодзи, LLM-судья «похоже ли на него»).
Стенд появляется до RAG, чтобы улучшения измерялись.

## LLM и эмбеддинги

- LLM: DeepSeek через OpenAI-совместимый API (`base_url`, `model`, ключ из env). Провайдер заменяем без правок шагов.
- Эмбеддинги: считаются локально (у DeepSeek нет эндпоинта эмбеддингов). Конкретная модель и библиотека выбираются на этапе RAG
  (кандидаты: fastembed/ONNX как лёгкий вариант, sentence-transformers как тяжёлый).

## Развёртывание

Docker Compose, два сервиса: `bot` (Python 3.12) и `db` (образ `pgvector/pgvector:pg16`), том для данных Postgres,
том `./data/imports` для экспортов. Бот работает через long polling, домен и открытые порты не нужны.
Секреты только в `.env`. Порт Postgres наружу не публикуется (или `127.0.0.1:5433`, чтобы не конфликтовать с локальным Postgres).
Перенос на VPS = копирование репозитория и `docker compose up -d`.

## Telegram Business: особенности

- Бот должен иметь включённый Business Mode (BotFather) и быть подключён в Автоматизации чатов.
- Апдейты: `business_connection`, `business_message`, `edited_business_message`, `deleted_business_messages`.
  В `allowed_updates` их нужно запросить явно.
- Ответ: `send_message(..., business_connection_id=...)`.
- В `business_message` приходят и сообщения самого владельца, и (возможно) эхо ответов бота. Эхо фильтруется по сохранённым message_id.
- Если Premium владельца заканчивается, подключение отключается (`business_connection.is_enabled=false`): бот уведомляет владельца.
- Telegram-уровень фильтрации чатов (исключения, выбранные чаты) — первый слой защиты, rules engine — второй.
