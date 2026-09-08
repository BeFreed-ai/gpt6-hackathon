from __future__ import annotations

import hashlib
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
            CREATE TABLE IF NOT EXISTS world_checkpoints (
                slot INTEGER PRIMARY KEY CHECK (slot = 1),
                saved_at TEXT NOT NULL,
                checksum TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                run_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                response_id TEXT,
                usage TEXT NOT NULL DEFAULT '{}',
                error_type TEXT
            );
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
            self._connection.execute("DELETE FROM world_checkpoints")
            self._connection.commit()

    def save_checkpoint(self, data: dict) -> None:
        encoded = json.dumps(data, separators=(",", ":"), allow_nan=False)
        checksum = hashlib.sha256(encoded.encode()).hexdigest()
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO world_checkpoints VALUES "
                "(1, strftime('%Y-%m-%dT%H:%M:%fZ','now'), ?, ?)",
                (checksum, encoded),
            )
            self._connection.commit()

    def load_checkpoint(self) -> dict | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT checksum, data FROM world_checkpoints WHERE slot = 1"
            ).fetchone()
        if row is None:
            return None
        checksum, encoded = row
        if hashlib.sha256(encoded.encode()).hexdigest() != checksum:
            raise ValueError("World checkpoint checksum mismatch; database left untouched")
        return json.loads(encoded)

    def sequence_high_water(self, run_id: str) -> tuple[int, int]:
        def high_water(table: str) -> int:
            rows = self._connection.execute(
                f"SELECT id FROM {table} WHERE id LIKE ?", (run_id + "_%",)
            ).fetchall()
            suffixes = (row[0].rsplit("_", 1)[-1] for row in rows)
            return max((int(suffix) for suffix in suffixes if suffix.isdigit()), default=0)

        with self._lock:
            return high_water("world_events"), high_water("agent_memories")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def start_call(self, run_id: str, agent_id: str, provider: str, model: str) -> int:
        with self._lock:
            cursor = self._connection.execute(
                "INSERT INTO model_calls (started_at, run_id, agent_id, provider, model, status) "
                "VALUES (strftime('%Y-%m-%dT%H:%M:%fZ','now'), ?, ?, ?, ?, 'started')",
                (run_id, agent_id, provider, model),
            )
            self._connection.commit()
            return cursor.lastrowid

    def finish_call(
        self,
        call_id: int,
        status: str,
        usage: dict | None = None,
        response_id: str | None = None,
        error_type: str | None = None,
    ) -> None:
        with self._lock:
            self._connection.execute(
                "UPDATE model_calls SET status=?, usage=?, response_id=?, error_type=? WHERE id=?",
                (status, json.dumps(usage or {}), response_id, error_type, call_id),
            )
            self._connection.commit()

    def call_count(self, run_id: str) -> int:
        with self._lock:
            return self._connection.execute(
                "SELECT count(*) FROM model_calls WHERE run_id=?", (run_id,)
            ).fetchone()[0]
