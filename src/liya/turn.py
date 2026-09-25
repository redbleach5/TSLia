from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Turn:
    turn_id: int
    reply_id: str
    generation: int
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class TurnManager:
    """Manages conversational turn lifecycle, cancellation events, and task tracking."""

    def __init__(self) -> None:
        self.generation: int = 0
        self.active_turn_id: int | None = None
        self.active_reply: str | None = None
        self.cancel_event: asyncio.Event | None = None
        self.active_turn: Turn | None = None

        self.tts_tasks: list[tuple[int, asyncio.Task]] = []
        self.llm_tasks: list[asyncio.Task] = []
        self.preemptive_tasks: dict[int, asyncio.Task] = {}
        self.active_task: asyncio.Task | None = None
        self._tts_dispatcher: asyncio.Task | None = None

    def begin_turn(self, request_id: int) -> int:
        self.generation += 1
        self.active_turn_id = self.generation
        self.active_reply = f"reply-{request_id}-{self.generation}"
        self.cancel_event = asyncio.Event()
        self.active_turn = Turn(
            turn_id=self.active_turn_id,
            reply_id=self.active_reply,
            generation=self.generation,
            cancel_event=self.cancel_event,
        )
        return self.generation

    def event_stamp(self, turn_id: int | None = None) -> dict[str, Any]:
        """Поля turn_id/generation для WebSocket events.

        Без аргумента — штамп текущей активной turn. С аргументом — штамп
        указанной turn: событие, отправленное задачей уже после смены turn,
        сохраняет свой generation и может быть отфильтровано клиентом.
        """
        if turn_id is None:
            return {"turn_id": self.active_turn_id, "generation": self.generation}
        return {"turn_id": turn_id, "generation": turn_id}

    def is_current(self, turn_id: int | None) -> bool:
        return (
            turn_id is not None
            and turn_id == self.active_turn_id
            and self.generation == turn_id
        )

    def cancel_active(self) -> None:
        if self.cancel_event:
            self.cancel_event.set()
        for task in [*self.tts_tasks, *self.llm_tasks, *self.preemptive_tasks.values()]:
            if not task.done():
                task.cancel()
        if self.active_task and not self.active_task.done():
            self.active_task.cancel()
        if self._tts_dispatcher and not self._tts_dispatcher.done():
            self._tts_dispatcher.cancel()
