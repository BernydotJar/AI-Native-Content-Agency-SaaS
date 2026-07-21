from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Sequence, Tuple, Union

from .models import (
    MemoryObservation,
    MemoryRecord,
    MemorySearchResult,
    Provenance,
)
from .utils import canonical_json, require_confidence, stable_id


Clock = Callable[[], str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SQLiteMemory:
    """Persistent Observe/Store/Search/Recall memory with source metadata.

    `observe` creates a validated candidate and does not mutate storage. `store`
    is the explicit persistence boundary. Search is local SQL only; no embeddings
    or external model calls are made.
    """

    def __init__(
        self,
        path: Union[str, Path] = ":memory:",
        clock: Clock = utc_now,
    ) -> None:
        self.path = str(path)
        self._clock = clock
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                INSERT OR IGNORE INTO schema_meta(key, value)
                VALUES ('schema_version', '1');

                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    observation_id TEXT NOT NULL UNIQUE,
                    content TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                    tags_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    stored_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memories_confidence
                    ON memories(confidence DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_stored_at
                    ON memories(stored_at DESC);
                """
            )

    def observe(
        self,
        content: str,
        provenance: Provenance,
        confidence: float,
        tags: Sequence[str] = (),
    ) -> MemoryObservation:
        require_confidence(confidence)
        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("content must not be empty")
        normalized_tags = tuple(
            sorted({tag.strip().lower() for tag in tags if tag and tag.strip()})
        )
        observed_at = self._clock()
        observation_id = stable_id(
            "obs",
            normalized_content,
            provenance,
            confidence,
            normalized_tags,
            observed_at,
        )
        return MemoryObservation(
            observation_id=observation_id,
            content=normalized_content,
            provenance=provenance,
            confidence=confidence,
            tags=normalized_tags,
            observed_at=observed_at,
        )

    def store(self, observation: MemoryObservation) -> MemoryRecord:
        memory_id = stable_id("mem", observation.observation_id)
        stored_at = self._clock()
        provenance_json = canonical_json(observation.provenance)
        tags_json = canonical_json(observation.tags)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO memories(
                    memory_id,
                    observation_id,
                    content,
                    provenance_json,
                    confidence,
                    tags_json,
                    observed_at,
                    stored_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    observation.observation_id,
                    observation.content,
                    provenance_json,
                    observation.confidence,
                    tags_json,
                    observation.observed_at,
                    stored_at,
                ),
            )
        return self.recall(memory_id)

    def search(
        self,
        query: str,
        limit: int = 10,
        min_confidence: float = 0.0,
    ) -> Tuple[MemorySearchResult, ...]:
        require_confidence(min_confidence)
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        tokens = tuple(
            dict.fromkeys(token for token in query.lower().split() if token.strip())
        )
        if not tokens:
            raise ValueError("query must not be empty")

        clauses = []
        parameters: List[object] = [min_confidence]
        for token in tokens:
            clauses.append("(lower(content) LIKE ? OR lower(tags_json) LIKE ?)")
            wildcard = "%{}%".format(token)
            parameters.extend((wildcard, wildcard))
        parameters.append(limit)
        sql = """
            SELECT * FROM memories
            WHERE confidence >= ? AND {}
            ORDER BY confidence DESC, stored_at DESC, memory_id ASC
            LIMIT ?
        """.format(" AND ".join(clauses))

        with self._lock:
            rows = self._connection.execute(sql, tuple(parameters)).fetchall()
        results = []
        for row in rows:
            record = self._row_to_record(row)
            content = record.content.lower()
            tags = set(record.tags)
            matched = sum(1 for token in tokens if token in content or token in tags)
            exact_tag_bonus = 0.1 if any(token in tags for token in tokens) else 0.0
            score = min(
                1.0,
                record.confidence * 0.55
                + (matched / len(tokens)) * 0.35
                + exact_tag_bonus,
            )
            results.append(MemorySearchResult(record=record, score=round(score, 4)))
        return tuple(sorted(results, key=lambda item: (-item.score, item.record.memory_id)))

    def recall(self, memory_id: str) -> MemoryRecord:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM memories WHERE memory_id = ?", (memory_id,)
            ).fetchone()
        if row is None:
            raise KeyError("memory not found: {}".format(memory_id))
        return self._row_to_record(row)

    def count(self) -> int:
        with self._lock:
            row = self._connection.execute("SELECT COUNT(*) AS total FROM memories").fetchone()
        return int(row["total"])

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "SQLiteMemory":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        provenance_data = json.loads(row["provenance_json"])
        return MemoryRecord(
            memory_id=row["memory_id"],
            content=row["content"],
            provenance=Provenance(**provenance_data),
            confidence=float(row["confidence"]),
            tags=tuple(json.loads(row["tags_json"])),
            observed_at=row["observed_at"],
            stored_at=row["stored_at"],
        )
