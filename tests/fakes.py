from __future__ import annotations

from tgtwin.core.models import IncomingMessage
from tgtwin.core.protocols import Sender


class FakeSender(Sender):
    def __init__(self) -> None:
        self.sent: list[tuple[IncomingMessage, str, float]] = []
        self.notified: list[tuple[str, str]] = []

    async def send(self, msg: IncomingMessage, text: str, delay: float) -> int | None:
        self.sent.append((msg, text, delay))
        return 12345

    async def notify_owner(self, connection_id: str, text: str) -> None:
        self.notified.append((connection_id, text))
