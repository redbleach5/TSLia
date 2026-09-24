from __future__ import annotations

import queue
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from .clients import LocalClients

@dataclass
class VoiceResult:
    transcript: str
    reply: str
    audio_path: Path

class VoicePipeline:
    def __init__(self, clients: LocalClients) -> None:
        self.clients = clients
        self._cancel = threading.Event()
        self._jobs: queue.Queue[Path | None] = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def submit(self, audio_path: str | Path) -> None:
        self._jobs.put(Path(audio_path))

    def cancel(self) -> None:
        self._cancel.set()
        self._jobs.queue.clear()

    def _run(self) -> None:
        while True:
            path = self._jobs.get()
            if path is None:
                return
            self._cancel.clear()
            try:
                transcript = self.clients.transcribe(path)
                if not self._cancel.is_set():
                    reply = self.clients.chat([{"role": "system", "content": "Ты — Лия. Отвечай кратко и естественно."}, {"role": "user", "content": transcript}])
                    if not self._cancel.is_set():
                        output = self.clients.speak(reply)
                        print(f"Вы: {transcript}\nЛия: {reply}\nАудио: {output}")
            except Exception as exc:
                if not self._cancel.is_set():
                    print(f"Ошибка голосового задания: {exc}", file=sys.stderr)
            finally:
                self._jobs.task_done()

    def close(self) -> None:
        self._jobs.put(None)
        self._worker.join(timeout=1)