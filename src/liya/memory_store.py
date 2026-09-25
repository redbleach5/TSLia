from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class MemoryFact:
    id: int
    kind: str
    content: str
    source: str

class MemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(kind, content))")
    def _connect(self):
        return sqlite3.connect(self.path)
    def add(self, content: str, kind: str = "fact", source: str = "conversation") -> MemoryFact | None:
        content = content.strip()
        if len(content) < 3: return None
        with self._connect() as db:
            db.execute("INSERT OR IGNORE INTO facts(kind, content, source) VALUES (?, ?, ?)", (kind, content, source))
            row = db.execute("SELECT id, kind, content, source FROM facts WHERE kind=? AND content=?", (kind, content)).fetchone()
        return MemoryFact(*row) if row else None
    def extract(self, text: str) -> list[MemoryFact]:
        facts: list[MemoryFact] = []
        patterns = [(r"меня зовут\s+([А-ЯЁа-яё][\w-]+)", "name"), (r"я предпочитаю\s+(.+)", "preference"), (r"мне нравится\s+(.+)", "preference"), (r"мой любимый\s+(.+) ", "preference")]
        for pattern, kind in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match: fact = self.add(match.group(0).strip(), kind); facts.extend([fact] if fact else [])
        return facts
    def search(self, query: str, limit: int = 5) -> list[MemoryFact]:
        terms = [term for term in re.findall(r"\w+", query.lower(), re.UNICODE) if len(term) > 2]
        if not terms: return []
        query_tokens = set(terms)
        found = [fact for fact in self.list(500) if query_tokens.intersection(set(re.findall(r"\w+", fact.content.casefold(), re.UNICODE)))]
        return found[:limit]
    def list(self, limit: int = 50) -> list[MemoryFact]:
        with self._connect() as db: rows = db.execute("SELECT id, kind, content, source FROM facts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [MemoryFact(*row) for row in rows]
    def delete(self, fact_id: int) -> bool:
        with self._connect() as db: return db.execute("DELETE FROM facts WHERE id=?", (fact_id,)).rowcount > 0