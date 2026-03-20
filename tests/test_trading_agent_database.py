import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "database" / "trading_agent_database.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("trading_agent_database", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TradingAgentDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_normalize_action_accepts_string(self):
        self.assertEqual(
            self.module.normalize_action("buy"),
            self.module.Action.BUY,
        )

    def test_normalize_action_accepts_json_string_payload(self):
        self.assertEqual(
            self.module.normalize_action('{"action":"sell"}'),
            self.module.Action.SELL,
        )

    def test_initialize_creates_updated_at_column(self):
        with tempfile.TemporaryDirectory(prefix="trading-agent-db-") as tmpdir:
            db_path = Path(tmpdir) / "trading_agent.db"
            database = self.module.TradingAgentDatabase(db_path)
            database.initialize()

            with sqlite3.connect(db_path) as conn:
                columns = conn.execute("PRAGMA table_info(trading_agent_runs)").fetchall()

            column_names = [column[1] for column in columns]
            self.assertIn("updated_at", column_names)
            self.assertIn("mode", column_names)

    def test_save_run_upserts_by_run_id(self):
        with tempfile.TemporaryDirectory(prefix="trading-agent-db-") as tmpdir:
            db_path = Path(tmpdir) / "trading_agent.db"
            database = self.module.TradingAgentDatabase(db_path)

            database.save_run(
                stock_code="600519",
                mode="polling",
                result_payload="buy",
                run_id="run-1",
            )
            database.save_run(
                stock_code="600519",
                mode="streaming",
                result_payload="hold",
                run_id="run-1",
            )

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT run_id, stock_code, mode, action FROM trading_agent_runs"
                ).fetchall()

            self.assertEqual(rows, [("run-1", "600519", "streaming", "hold")])

    def test_initialize_adds_mode_column_to_existing_table(self):
        with tempfile.TemporaryDirectory(prefix="trading-agent-db-") as tmpdir:
            db_path = Path(tmpdir) / "trading_agent.db"

            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE trading_agent_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL UNIQUE,
                        stock_code TEXT NOT NULL,
                        action TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        raw_result TEXT
                    )
                    """
                )

            database = self.module.TradingAgentDatabase(db_path)
            database.initialize()

            with sqlite3.connect(db_path) as conn:
                columns = conn.execute("PRAGMA table_info(trading_agent_runs)").fetchall()

            column_names = [column[1] for column in columns]
            self.assertIn("mode", column_names)
