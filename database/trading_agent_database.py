"""
Minimal SQLite database for trading-agent run results.
"""

from __future__ import annotations

import json
import sqlite3
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class Action(Enum):
    """Execution actions for order placement."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


def default_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".runtime" / "database" / "trading_agent.db"


def _json_load_if_possible(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _extract_candidate(payload: Any) -> Any:
    current = payload
    if isinstance(current, str):
        current = _json_load_if_possible(current)

    if isinstance(current, dict):
        for key in ("action", "trading_action", "decision", "signal", "result"):
            value = current.get(key)
            if value is not None:
                return value
    return current


def normalize_action(payload: Any) -> Action:
    candidate = _extract_candidate(payload)

    if isinstance(candidate, Action):
        return candidate

    if isinstance(candidate, bool):
        return Action.BUY if candidate else Action.HOLD

    if isinstance(candidate, str):
        normalized = candidate.strip().lower()
        mapping = {
            "buy": Action.BUY,
            "indicating": Action.BUY,
            "true": Action.BUY,
            "sell": Action.SELL,
            "hold": Action.HOLD,
            "not_indicating": Action.HOLD,
            "false": Action.HOLD,
        }
        if normalized in mapping:
            return mapping[normalized]

    raise ValueError(f"Unsupported action payload: {payload!r}")


def serialize_raw_result(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class TradingAgentDatabase:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else default_db_path()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trading_agent_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL UNIQUE,
                    stock_code TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'polling' CHECK (mode IN ('streaming', 'polling')),
                    action TEXT NOT NULL CHECK (action IN ('buy', 'sell', 'hold')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    raw_result TEXT
                )
                """
            )
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(trading_agent_runs)").fetchall()
            }
            if "mode" not in columns:
                conn.execute(
                    """
                    ALTER TABLE trading_agent_runs
                    ADD COLUMN mode TEXT NOT NULL DEFAULT 'polling'
                    """
                )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_trading_agent_runs_stock_code
                ON trading_agent_runs (stock_code)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_trading_agent_runs_created_at
                ON trading_agent_runs (created_at)
                """
            )

    def save_run(self, *, stock_code: str, mode: str, result_payload: Any, run_id: str | None = None) -> str:
        self.initialize()
        effective_run_id = run_id or uuid4().hex
        action = normalize_action(result_payload)
        raw_result = serialize_raw_result(result_payload)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO trading_agent_runs (run_id, stock_code, mode, action, raw_result)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    stock_code = excluded.stock_code,
                    mode = excluded.mode,
                    action = excluded.action,
                    raw_result = excluded.raw_result,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (effective_run_id, stock_code, mode, action.value, raw_result),
            )

        return effective_run_id
