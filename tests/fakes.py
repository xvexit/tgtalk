from __future__ import annotations

from datetime import UTC, datetime

from tgtwin.core.models import HistoryItem, IncomingMessage, ReplyLogEntry, StoredMessage
from tgtwin.core.protocols import MessageRepository, ReplyLogRepository, Sender


class FakeSender(Sender):
    def __init__(self) -> None:
        self.sent: list[tuple[IncomingMessage, str, float]] = []
        self.notified: list[tuple[str, str]] = []

    async def send(self, msg: IncomingMessage, text: str, delay: float) -> int | None:
        self.sent.append((msg, text, delay))
        return 12345

    async def notify_owner(self, connection_id: str, text: str) -> None:
        self.notified.append((connection_id, text))


class FakeMessageRepo(MessageRepository):
    def __init__(self) -> None:
        self.rows: dict[tuple[int, int], StoredMessage] = {}
        self.added: list[StoredMessage] = []
        self.last_owner: datetime | None = None

    async def add(self, msg: StoredMessage) -> None:
        key = (msg.chat_id, msg.message_id)
        if key in self.rows:
            return
        self.rows[key] = msg
        self.added.append(msg)

    async def exists(self, chat_id: int, message_id: int) -> bool:
        return (chat_id, message_id) in self.rows

    async def role_of(self, chat_id: int, message_id: int) -> str | None:
        msg = self.rows.get((chat_id, message_id))
        return msg.role if msg else None

    async def last(self, chat_id: int, n: int) -> list[HistoryItem]:
        items = [
            HistoryItem(message_id=m.message_id, role=m.role, text=m.text or "", ts=m.ts)
            for (c, _), m in sorted(self.rows.items(), key=lambda kv: kv[1].ts)
            if c == chat_id
        ]
        return items[-n:]

    async def last_owner_ts(self, chat_id: int) -> datetime | None:
        return self.last_owner

    def seed(self, chat_id: int, message_id: int, role: str, text: str = "x") -> None:
        self.rows[(chat_id, message_id)] = StoredMessage(
            chat_id=chat_id,
            message_id=message_id,
            role=role,
            text=text,
            ts=datetime.now(UTC),
        )


class FakeReplyLogRepo(ReplyLogRepository):
    def __init__(self, sent_count: int = 0) -> None:
        self.entries: list[tuple[int, ReplyLogEntry]] = []
        self.next_id = 1
        self.sent_count = sent_count
        self.marked: list[tuple[int, bool]] = []

    async def add(self, entry: ReplyLogEntry) -> int:
        log_id = self.next_id
        self.next_id += 1
        self.entries.append((log_id, entry))
        return log_id

    async def mark_sent(self, log_id: int, sent: bool) -> None:
        self.marked.append((log_id, sent))

    async def count_sent_since(self, chat_id: int, since: datetime) -> int:
        return self.sent_count


class DummySent:
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id


class DummyBot:
    def __init__(self, next_message_id: int = 200) -> None:
        self.next_message_id = next_message_id
        self.send_message_calls = 0
        self.send_chat_action_calls = 0
        self.notify_calls = 0

    async def send_chat_action(self, *args, **kwargs) -> None:
        self.send_chat_action_calls += 1
        self.last_chat_action_kwargs = kwargs

    async def send_message(self, *args, **kwargs) -> DummySent:
        self.send_message_calls += 1
        self.last_send_kwargs = kwargs
        return DummySent(self.next_message_id)

    async def get_business_connection(self, *args, **kwargs):
        return None


class DummyChat:
    def __init__(self, chat_id: int, full_name: str | None = None, username: str | None = None) -> None:
        self.id = chat_id
        self.full_name = full_name
        self.username = username


class DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class DummyMsg:
    def __init__(
        self,
        message_id: int,
        chat: DummyChat,
        text: str,
        from_user_id: int,
        date: datetime,
        business_connection_id: str = "bc1",
    ) -> None:
        self.message_id = message_id
        self.chat = chat
        self.text = text
        self.from_user = DummyUser(from_user_id)
        self.date = date
        self.business_connection_id = business_connection_id
