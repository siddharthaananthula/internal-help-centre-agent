import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "agent_calls.db"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                question TEXT NOT NULL,
                tools_called TEXT NOT NULL,
                chunk_ids TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                latency_ms INTEGER NOT NULL,
                final_outcome TEXT NOT NULL
            )
            """
        )


def log_call(
    timestamp: str,
    question: str,
    tools_called: list[str],
    chunk_ids: list[str],
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: int,
    final_outcome: str,
) -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO agent_calls (
                timestamp, question, tools_called, chunk_ids, input_tokens,
                output_tokens, cost_usd, latency_ms, final_outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                question,
                ",".join(tools_called),
                ",".join(chunk_ids),
                input_tokens,
                output_tokens,
                cost_usd,
                latency_ms,
                final_outcome,
            ),
        )
