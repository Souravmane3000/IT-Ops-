"""Thread-safe SSE event publisher."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ExecutionEvent:
    run_id: str
    event_type: str
    message: str
    status: str = "info"
    action_id: str | None = None
    timestamp: str = field(default_factory=utc_now)
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data["details"] is None:
            del data["details"]
        return data

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.to_dict())}\n\n"


class EventPublisher:
    """Per-run asyncio queues with thread-safe publish from worker threads."""

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = {}
        self._history: dict[str, list[ExecutionEvent]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = asyncio.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._queues.setdefault(run_id, []).append(queue)
            for event in self._history.get(run_id, []):
                await queue.put(event)
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            queues = self._queues.get(run_id, [])
            if queue in queues:
                queues.remove(queue)

    def publish(self, event: ExecutionEvent) -> None:
        """Publish from any thread. Uses call_soon_threadsafe when needed."""
        self._history.setdefault(event.run_id, []).append(event)

        loop = self._loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
                self._loop = loop
            except RuntimeError:
                return

        def _put() -> None:
            for queue in list(self._queues.get(event.run_id, [])):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is loop:
            _put()
        else:
            loop.call_soon_threadsafe(_put)

    def publish_simple(
        self,
        run_id: str,
        event_type: str,
        message: str,
        *,
        status: str = "info",
        action_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.publish(
            ExecutionEvent(
                run_id=run_id,
                event_type=event_type,
                message=message,
                status=status,
                action_id=action_id,
                details=details,
            )
        )


_publisher: EventPublisher | None = None


def get_event_publisher() -> EventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher()
    return _publisher
