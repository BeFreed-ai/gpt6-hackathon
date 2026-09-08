from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from app.models import Memory, WorldEvent


class EventStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS world_events (
                id TEXT PRIMARY KEY,
                world_time REAL NOT NULL,
                event_type TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_memories (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                world_time REAL NOT NULL,
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memories_agent_time
                ON agent_memories(agent_id, world_time);
            """
        )
        self._connection.commit()

    def append_event(self, event: WorldEvent) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO world_events VALUES (?, ?, ?, ?)",
                (event.id, event.world_time, event.type, event.model_dump_json()),
            )
            self._connection.commit()

    def append_memory(self, agent_id: str, memory: Memory) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO agent_memories VALUES (?, ?, ?, ?)",
                (memory.id, agent_id, memory.world_time, memory.model_dump_json()),
            )
            self._connection.commit()

    def recent_events(self, limit: int = 80) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT data FROM world_events ORDER BY world_time DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]

    def clear(self) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM world_events")
            self._connection.execute("DELETE FROM agent_memories")
            self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()
