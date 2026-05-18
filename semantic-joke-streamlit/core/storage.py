from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from schemas import JokeResult


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = APP_DIR / "data" / "jokes.sqlite3"


@dataclass(frozen=True)
class StoredJoke:
    id: int
    created_at: str
    pipeline_id: str
    pipeline_name: str
    topic: str
    audience: str
    voice: str
    format: str
    constraints_json: str
    best_joke: str
    model: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None
    duration_seconds: float | None
    result_json: str


CREATE_JOKES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jokes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    pipeline_id TEXT NOT NULL,
    pipeline_name TEXT NOT NULL,
    topic TEXT NOT NULL,
    audience TEXT NOT NULL,
    voice TEXT NOT NULL,
    format TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    best_joke TEXT NOT NULL,
    model TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    estimated_cost_usd REAL,
    duration_seconds REAL,
    result_json TEXT NOT NULL
)
""".strip()


def connect(database_path: Path = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_database(database_path: Path = DEFAULT_DATABASE_PATH) -> None:
    with connect(database_path) as connection:
        connection.execute(CREATE_JOKES_TABLE_SQL)


def save_joke_result(
    pipeline_id: str,
    pipeline_name: str,
    result: JokeResult,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> int:
    init_database(database_path)
    usage = result.usage
    with connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO jokes (
                created_at,
                pipeline_id,
                pipeline_name,
                topic,
                audience,
                voice,
                format,
                constraints_json,
                best_joke,
                model,
                input_tokens,
                output_tokens,
                total_tokens,
                estimated_cost_usd,
                duration_seconds,
                result_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).isoformat(),
                pipeline_id,
                pipeline_name,
                result.request.topic,
                result.request.audience,
                result.request.voice,
                result.request.format,
                json.dumps(result.request.constraints, ensure_ascii=False),
                result.best_joke.text,
                usage.model if usage is not None else None,
                usage.input_tokens if usage is not None else 0,
                usage.output_tokens if usage is not None else 0,
                usage.total_tokens if usage is not None else 0,
                usage.estimated_cost_usd if usage is not None else None,
                usage.duration_seconds if usage is not None else None,
                result.model_dump_json(),
            ),
        )
        return int(cursor.lastrowid)


def save_joke_results(
    results: dict[str, JokeResult],
    pipeline_names: dict[str, str],
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> list[int]:
    return [
        save_joke_result(pipeline_id, pipeline_names[pipeline_id], result, database_path)
        for pipeline_id, result in results.items()
    ]


def list_jokes(search: str = "", database_path: Path = DEFAULT_DATABASE_PATH) -> list[StoredJoke]:
    init_database(database_path)
    search_text = search.strip()
    with connect(database_path) as connection:
        if search_text:
            pattern = f"%{search_text}%"
            rows = connection.execute(
                """
                SELECT * FROM jokes
                WHERE topic LIKE ?
                   OR pipeline_name LIKE ?
                   OR model LIKE ?
                   OR best_joke LIKE ?
                ORDER BY created_at DESC, id DESC
                """,
                (pattern, pattern, pattern, pattern),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM jokes ORDER BY created_at DESC, id DESC"
            ).fetchall()
    return [StoredJoke(**dict(row)) for row in rows]


def get_joke(joke_id: int, database_path: Path = DEFAULT_DATABASE_PATH) -> StoredJoke | None:
    init_database(database_path)
    with connect(database_path) as connection:
        row = connection.execute("SELECT * FROM jokes WHERE id = ?", (joke_id,)).fetchone()
    return StoredJoke(**dict(row)) if row is not None else None

