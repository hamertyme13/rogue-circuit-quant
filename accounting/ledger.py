import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEPOSIT = "DEPOSIT"
WITHDRAWAL = "WITHDRAWAL"


@dataclass
class LedgerSummary:

    deposits: float
    withdrawals: float
    net_deposits: float
    current_value: float
    net_growth: float
    growth_percent: float


@dataclass
class PortfolioSnapshot:

    timestamp: str
    total_value: float
    cash_value: float
    positions_value: float
    source: str


@dataclass
class BotControls:

    emergency_stop: bool
    max_order_notional: float
    min_signal_confidence: float
    loop_seconds: float


class InvestmentLedger:

    def __init__(self, db_path: str | Path):

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._initialize()

    def add_deposit(
        self,
        amount: float,
        note: str = "",
        currency: str = "USD",
    ):

        return self._add_transaction(
            DEPOSIT,
            amount,
            note,
            currency,
        )

    def add_withdrawal(
        self,
        amount: float,
        note: str = "",
        currency: str = "USD",
    ):

        return self._add_transaction(
            WITHDRAWAL,
            amount,
            note,
            currency,
        )

    def record_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fee: float = 0.0,
        pnl: float = 0.0,
        source: str = "manual",
    ):

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO trades (
                    symbol,
                    side,
                    quantity,
                    price,
                    fee,
                    pnl,
                    source,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    side.upper(),
                    float(quantity),
                    float(price),
                    float(fee),
                    float(pnl),
                    source,
                    self._now(),
                ),
            )

            return cursor.lastrowid

    def record_snapshot(
        self,
        total_value: float,
        cash_value: float = 0.0,
        positions_value: float = 0.0,
        source: str = "manual",
    ):

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO portfolio_snapshots (
                    total_value,
                    cash_value,
                    positions_value,
                    source,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    float(total_value),
                    float(cash_value),
                    float(positions_value),
                    source,
                    self._now(),
                ),
            )

            return cursor.lastrowid

    def record_decision(
        self,
        symbol: str,
        strategy: str,
        action: str,
        confidence: float,
        price: float,
        executed: bool,
        quantity: float = 0.0,
        reason: str = "",
        order_id: str = "",
        mode: str = "paper",
    ):

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO decisions (
                    symbol,
                    strategy,
                    action,
                    confidence,
                    price,
                    executed,
                    quantity,
                    reason,
                    order_id,
                    mode,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    strategy,
                    action,
                    float(confidence),
                    float(price),
                    int(executed),
                    float(quantity),
                    reason,
                    order_id,
                    mode,
                    self._now(),
                ),
            )

            return cursor.lastrowid

    def record_strategy_performance(
        self,
        symbol: str,
        strategy: str,
        score: float,
        net_profit: float,
        win_rate: float,
        drawdown: float,
        trades: int,
        rationale: str = "",
    ):

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO strategy_performance (
                    symbol,
                    strategy,
                    score,
                    net_profit,
                    win_rate,
                    drawdown,
                    trades,
                    rationale,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    strategy,
                    float(score),
                    float(net_profit),
                    float(win_rate),
                    float(drawdown),
                    int(trades),
                    rationale,
                    self._now(),
                ),
            )

            return cursor.lastrowid

    def add_alert(
        self,
        level: str,
        message: str,
        source: str = "dashboard",
    ):

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO alerts (
                    level,
                    message,
                    source,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    level.upper(),
                    message,
                    source,
                    self._now(),
                ),
            )

            return cursor.lastrowid

    def record_audit_event(
        self,
        actor: str,
        action: str,
        detail: str,
        source: str = "system",
    ):

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_log (
                    actor,
                    action,
                    detail,
                    source,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    actor,
                    action,
                    detail,
                    source,
                    self._now(),
                ),
            )

            return cursor.lastrowid

    def record_paper_live_comparison(
        self,
        symbol: str,
        paper_action: str,
        live_action: str,
        paper_price: float,
        live_price: float,
        difference: float,
        reason: str = "",
    ):

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO paper_live_comparison (
                    symbol,
                    paper_action,
                    live_action,
                    paper_price,
                    live_price,
                    difference,
                    reason,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    paper_action,
                    live_action,
                    float(paper_price),
                    float(live_price),
                    float(difference),
                    reason,
                    self._now(),
                ),
            )

            return cursor.lastrowid

    def record_shadow_observation(
        self,
        symbol: str,
        action: str,
        strategy: str,
        confidence: float,
        entry_price: float,
        quantity: float,
        valid: bool,
        cost_rate: float,
        reason: str = "",
    ):
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO shadow_observations (
                    symbol, action, strategy, confidence, entry_price,
                    quantity, valid, cost_rate, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol, action.upper(), strategy, float(confidence),
                    float(entry_price), float(quantity), int(valid),
                    float(cost_rate), reason, self._now(),
                ),
            )
            return cursor.lastrowid

    def resolve_shadow_observations(self, symbol: str, current_price: float):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, action, entry_price, cost_rate
                FROM shadow_observations
                WHERE symbol = ? AND resolved_at IS NULL
                """,
                (symbol,),
            ).fetchall()
            resolved_at = self._now()
            for row in rows:
                entry = float(row["entry_price"])
                gross = (float(current_price) / entry - 1.0) if entry else 0.0
                if row["action"] == "SELL":
                    gross = -gross
                net = gross - float(row["cost_rate"])
                conn.execute(
                    """
                    UPDATE shadow_observations
                    SET exit_price = ?, gross_return = ?, net_return = ?,
                        resolved_at = ?
                    WHERE id = ?
                    """,
                    (float(current_price), gross, net, resolved_at, row["id"]),
                )
            return len(rows)

    def set_setting(
        self,
        key: str,
        value: str | int | float | bool,
    ):

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (
                    key,
                    value,
                    updated_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(key)
                DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    str(value),
                    self._now(),
                ),
            )

    def get_setting(
        self,
        key: str,
        default: str = "",
    ) -> str:

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT value
                FROM settings
                WHERE key = ?
                """,
                (key,),
            ).fetchone()

        if row is None:
            return default

        return row["value"]

    def set_json_setting(self, key: str, value):
        self.set_setting(key, json.dumps(value, separators=(",", ":")))

    def get_json_setting(self, key: str, default=None):
        raw = self.get_setting(key, "")
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return default

    def set_emergency_stop(self, enabled: bool):

        self.set_setting(
            "emergency_stop",
            "1" if enabled else "0",
        )

    def bot_controls(
        self,
        max_order_notional: float,
        min_signal_confidence: float,
        loop_seconds: float,
    ) -> BotControls:

        return BotControls(
            emergency_stop=self.get_setting(
                "emergency_stop",
                "0",
            ) == "1",
            max_order_notional=float(
                self.get_setting(
                    "max_order_notional",
                    str(max_order_notional),
                )
            ),
            min_signal_confidence=float(
                self.get_setting(
                    "min_signal_confidence",
                    str(min_signal_confidence),
                )
            ),
            loop_seconds=float(
                self.get_setting(
                    "loop_seconds",
                    str(loop_seconds),
                )
            ),
        )

    def summary(
        self,
        snapshot_sources: tuple[str, ...] | None = None,
    ) -> LedgerSummary:

        deposits = self.total_transactions(DEPOSIT)
        withdrawals = self.total_transactions(WITHDRAWAL)
        net_deposits = deposits - withdrawals
        current_value = self.current_value(snapshot_sources)
        net_growth = current_value - net_deposits

        if net_deposits > 0:
            growth_percent = net_growth / net_deposits
        else:
            growth_percent = 0.0

        return LedgerSummary(
            deposits=deposits,
            withdrawals=withdrawals,
            net_deposits=net_deposits,
            current_value=current_value,
            net_growth=net_growth,
            growth_percent=growth_percent,
        )

    def total_transactions(self, transaction_type: str) -> float:

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE type = ?
                """,
                (transaction_type,),
            ).fetchone()

        return float(row[0])

    def current_value(
        self,
        snapshot_sources: tuple[str, ...] | None = None,
    ) -> float:

        latest = self.latest_snapshot(snapshot_sources)

        if latest is not None:
            return latest.total_value

        return (
            self.total_transactions(DEPOSIT)
            - self.total_transactions(WITHDRAWAL)
        )

    def latest_snapshot(
        self,
        sources: tuple[str, ...] | None = None,
    ) -> PortfolioSnapshot | None:

        source_clause, params = self._source_filter(sources)

        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT
                    created_at,
                    total_value,
                    cash_value,
                    positions_value,
                    source
                FROM portfolio_snapshots
                {source_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()

        if row is None:
            return None

        return PortfolioSnapshot(
            timestamp=row["created_at"],
            total_value=float(row["total_value"]),
            cash_value=float(row["cash_value"]),
            positions_value=float(row["positions_value"]),
            source=row["source"],
        )

    def snapshots(
        self,
        limit: int = 250,
        sources: tuple[str, ...] | None = None,
    ) -> list[PortfolioSnapshot]:

        source_clause, params = self._source_filter(sources)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    created_at,
                    total_value,
                    cash_value,
                    positions_value,
                    source
                FROM portfolio_snapshots
                {source_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()

        return [
            PortfolioSnapshot(
                timestamp=row["created_at"],
                total_value=float(row["total_value"]),
                cash_value=float(row["cash_value"]),
                positions_value=float(row["positions_value"]),
                source=row["source"],
            )
            for row in reversed(rows)
        ]

    def _source_filter(
        self,
        sources: tuple[str, ...] | None,
    ) -> tuple[str, tuple[str, ...]]:

        if not sources:
            return "", ()

        placeholders = ", ".join("?" for _ in sources)
        return f"WHERE source IN ({placeholders})", tuple(sources)

    def transactions(self, limit: int = 100):

        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    type,
                    amount,
                    currency,
                    note,
                    created_at
                FROM transactions
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def trades(self, limit: int = 100):

        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    symbol,
                    side,
                    quantity,
                    price,
                    fee,
                    pnl,
                    source,
                    created_at
                FROM trades
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def decisions(self, limit: int = 100):

        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    symbol,
                    strategy,
                    action,
                    confidence,
                    price,
                    executed,
                    quantity,
                    reason,
                    order_id,
                    mode,
                    created_at
                FROM decisions
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def strategy_performance(self, limit: int = 100):

        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    symbol,
                    strategy,
                    score,
                    net_profit,
                    win_rate,
                    drawdown,
                    trades,
                    rationale,
                    created_at
                FROM strategy_performance
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def alerts(self, limit: int = 100):

        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    level,
                    message,
                    source,
                    created_at
                FROM alerts
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def audit_log(self, limit: int = 100):

        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    actor,
                    action,
                    detail,
                    source,
                    created_at
                FROM audit_log
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def paper_live_comparisons(self, limit: int = 100):

        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    symbol,
                    paper_action,
                    live_action,
                    paper_price,
                    live_price,
                    difference,
                    reason,
                    created_at
                FROM paper_live_comparison
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def shadow_observations(self, limit: int = 500):
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT symbol, action, strategy, confidence, entry_price,
                       exit_price, quantity, valid, cost_rate, gross_return,
                       net_return, reason, created_at, resolved_at
                FROM shadow_observations
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def _add_transaction(
        self,
        transaction_type: str,
        amount: float,
        note: str,
        currency: str,
    ):

        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO transactions (
                    type,
                    amount,
                    currency,
                    note,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    transaction_type,
                    float(amount),
                    currency.upper(),
                    note,
                    self._now(),
                ),
            )

            return cursor.lastrowid

    def _initialize(self):

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_value REAL NOT NULL,
                    cash_value REAL NOT NULL,
                    positions_value REAL NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    fee REAL NOT NULL,
                    pnl REAL NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    price REAL NOT NULL,
                    executed INTEGER NOT NULL,
                    quantity REAL NOT NULL,
                    reason TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    score REAL NOT NULL,
                    net_profit REAL NOT NULL,
                    win_rate REAL NOT NULL,
                    drawdown REAL NOT NULL,
                    trades INTEGER NOT NULL,
                    rationale TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_live_comparison (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    paper_action TEXT NOT NULL,
                    live_action TEXT NOT NULL,
                    paper_price REAL NOT NULL,
                    live_price REAL NOT NULL,
                    difference REAL NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS shadow_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    quantity REAL NOT NULL,
                    valid INTEGER NOT NULL,
                    cost_rate REAL NOT NULL,
                    gross_return REAL,
                    net_return REAL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """
            )

    def _connect(self):

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _now(self) -> str:

        return datetime.now(timezone.utc).isoformat()
