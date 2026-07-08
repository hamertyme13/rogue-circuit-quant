import json
import mimetypes
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock
from urllib.parse import urlparse

from accounting.ledger import InvestmentLedger
from accounting.valuation import KrakenBalanceValuator
from config import (
    LEDGER_DB_PATH,
    LIVE_LOOP_SECONDS,
    MAX_ORDER_NOTIONAL,
    MIN_SIGNAL_CONFIDENCE,
    PORTFOLIO_ALERT_PERCENT,
)
from exchange.client import KrakenClient
from live.bot_service import TradingBotService
from live.trader import AutomatedKrakenTrader


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"


class WebCommandCenter:

    def __init__(self, ledger_path=LEDGER_DB_PATH):

        self.lock = RLock()
        self.ledger = InvestmentLedger(ledger_path)
        self.client = KrakenClient()
        self.valuator = KrakenBalanceValuator(self.client)
        self.trader = AutomatedKrakenTrader(
            client=self.client,
        )
        self._load_controls()
        self.service = TradingBotService(
            cycle_runner=self.run_one_cycle,
            loop_seconds=self.trader.loop_seconds,
            on_success=self._service_success,
            on_error=self._service_error,
            on_stop=self._service_stopped,
        )

    def state(self):

        with self.lock:
            summary = asdict(self.ledger.summary())
            controls = asdict(
                self.ledger.bot_controls(
                    max_order_notional=self.trader.max_order_notional,
                    min_signal_confidence=(
                        self.trader.min_signal_confidence
                    ),
                    loop_seconds=self.trader.loop_seconds,
                )
            )

            return {
                "summary": summary,
                "controls": controls,
                "service": {
                    "running": self.service.is_running(),
                    "emergency_stop": self.trader.kill_switch.active(),
                },
                "snapshots": [
                    asdict(snapshot)
                    for snapshot in self.ledger.snapshots()
                ],
                "transactions": [
                    self._row_dict(row)
                    for row in self.ledger.transactions()
                ],
                "trades": [
                    self._row_dict(row)
                    for row in self.ledger.trades()
                ],
                "decisions": [
                    self._row_dict(row)
                    for row in self.ledger.decisions()
                ],
                "strategies": [
                    self._row_dict(row)
                    for row in self.ledger.strategy_performance()
                ],
                "alerts": [
                    self._row_dict(row)
                    for row in self.ledger.alerts()
                ],
            }

    def add_deposit(self, payload):

        amount = self._amount(payload)
        note = payload.get("note", "")

        with self.lock:
            self.ledger.add_deposit(amount, note)

        return self.state()

    def add_withdrawal(self, payload):

        amount = self._amount(payload)
        note = payload.get("note", "")

        with self.lock:
            self.ledger.add_withdrawal(amount, note)

        return self.state()

    def record_manual_snapshot(self, payload):

        total_value = self._amount(payload)

        with self.lock:
            self.ledger.record_snapshot(
                total_value=total_value,
                cash_value=total_value,
                positions_value=0.0,
                source="browser_manual",
            )
            self._record_value_alerts(
                total_value,
                "browser_manual",
            )

        return self.state()

    def record_kraken_snapshot(self):

        valuation = self.valuator.snapshot()

        with self.lock:
            self.ledger.record_snapshot(
                total_value=valuation.total_value,
                cash_value=valuation.cash_value,
                positions_value=valuation.positions_value,
                source="kraken",
            )
            self._record_value_alerts(
                valuation.total_value,
                "kraken",
            )

        return self.state()

    def apply_settings(self, payload):

        max_order = self._positive_float(
            payload.get("max_order_notional")
        )
        min_confidence = float(payload.get("min_signal_confidence"))
        loop_seconds = self._positive_float(
            payload.get("loop_seconds")
        )

        if not 0 <= min_confidence <= 1:
            raise ValueError(
                "Minimum confidence must be between 0 and 1."
            )

        with self.lock:
            self.trader.max_order_notional = max_order
            self.trader.min_signal_confidence = min_confidence
            self.trader.loop_seconds = loop_seconds
            self.service.loop_seconds = loop_seconds
            self.ledger.set_setting(
                "max_order_notional",
                max_order,
            )
            self.ledger.set_setting(
                "min_signal_confidence",
                min_confidence,
            )
            self.ledger.set_setting(
                "loop_seconds",
                loop_seconds,
            )
            self.ledger.add_alert(
                "INFO",
                "Browser risk controls updated.",
                "browser",
            )

        return self.state()

    def run_one_cycle(self):

        with self.lock:
            events = self.trader.run_once()
            portfolio_value = self.trader.portfolio.account_value()

            self.ledger.record_snapshot(
                total_value=portfolio_value,
                cash_value=portfolio_value,
                positions_value=0.0,
                source="browser_paper_trader",
            )
            self._record_value_alerts(
                portfolio_value,
                "browser_paper_trader",
            )

            for event in events:
                self.ledger.record_decision(
                    symbol=event.symbol,
                    strategy=event.strategy,
                    action=event.action,
                    confidence=event.confidence,
                    price=event.price,
                    executed=event.executed,
                    quantity=event.quantity,
                    reason=event.reason,
                    order_id=event.order_id,
                    mode=event.mode,
                )

                if event.executed:
                    self.ledger.add_alert(
                        "INFO",
                        (
                            f"{event.mode.upper()} {event.action} "
                            f"{event.symbol} "
                            f"quantity={event.quantity:.8f}"
                        ),
                        "browser_trader",
                    )

            for performance in self.trader.strategy_performance.values():
                self.ledger.record_strategy_performance(
                    symbol=performance.symbol,
                    strategy=performance.strategy,
                    score=performance.score,
                    net_profit=performance.net_profit,
                    win_rate=performance.win_rate,
                    drawdown=performance.drawdown,
                    trades=performance.trades,
                    rationale=performance.rationale,
                )

            for trade in self.trader.portfolio.closed_trades:
                if getattr(trade, "_web_ledger_recorded", False):
                    continue

                self.ledger.record_trade(
                    symbol="paper",
                    side="SELL",
                    quantity=trade.quantity,
                    price=trade.exit_price,
                    pnl=trade.pnl,
                    source=trade.strategy,
                )
                trade._web_ledger_recorded = True

        return f"Trading cycle completed with {len(events)} event(s)."

    def run_one_cycle_response(self):

        message = self.run_one_cycle()
        state = self.state()
        state["message"] = message
        return state

    def start_service(self):

        if self.trader.kill_switch.active():
            raise RuntimeError(
                "Emergency stop is active. Resume before starting."
            )

        with self.lock:
            self.apply_settings({
                "max_order_notional": self.trader.max_order_notional,
                "min_signal_confidence": (
                    self.trader.min_signal_confidence
                ),
                "loop_seconds": self.trader.loop_seconds,
            })
            started = self.service.start()
            self.ledger.add_alert(
                "INFO",
                "Browser bot service started."
                if started
                else "Browser bot service already running.",
                "browser",
            )

        return self.state()

    def stop_service(self):

        self.service.stop()

        with self.lock:
            self.ledger.add_alert(
                "INFO",
                "Browser bot service stop requested.",
                "browser",
            )

        return self.state()

    def emergency_stop(self):

        self.service.stop()

        with self.lock:
            self.trader.emergency_stop()
            self.ledger.set_emergency_stop(True)
            self.ledger.add_alert(
                "CRITICAL",
                "Browser emergency stop activated.",
                "browser",
            )

        return self.state()

    def resume(self):

        with self.lock:
            self.trader.resume_trading()
            self.ledger.set_emergency_stop(False)
            self.ledger.add_alert(
                "INFO",
                "Browser trading resumed from emergency stop.",
                "browser",
            )

        return self.state()

    def _load_controls(self):

        controls = self.ledger.bot_controls(
            max_order_notional=MAX_ORDER_NOTIONAL,
            min_signal_confidence=MIN_SIGNAL_CONFIDENCE,
            loop_seconds=LIVE_LOOP_SECONDS,
        )
        self.trader.max_order_notional = controls.max_order_notional
        self.trader.min_signal_confidence = (
            controls.min_signal_confidence
        )
        self.trader.loop_seconds = controls.loop_seconds

        if controls.emergency_stop:
            self.trader.emergency_stop()

    def _service_success(self, message: str):

        with self.lock:
            self.ledger.add_alert(
                "INFO",
                message,
                "browser_service",
            )

    def _service_error(self, exc: Exception):

        with self.lock:
            self.ledger.add_alert(
                "ERROR",
                str(exc),
                "browser_service",
            )

    def _service_stopped(self):

        with self.lock:
            self.ledger.add_alert(
                "INFO",
                "Browser bot service stopped.",
                "browser_service",
            )

    def _record_value_alerts(
        self,
        total_value: float,
        source: str,
    ):

        snapshots = self.ledger.snapshots(limit=2)

        if len(snapshots) < 2:
            return

        previous = snapshots[-2].total_value

        if previous <= 0:
            return

        change_percent = (total_value - previous) / previous

        if abs(change_percent) < PORTFOLIO_ALERT_PERCENT:
            return

        direction = "up" if change_percent > 0 else "down"
        level = "INFO" if change_percent > 0 else "WARN"

        self.ledger.add_alert(
            level,
            (
                f"Portfolio {direction} {abs(change_percent):.2%} "
                f"from previous snapshot."
            ),
            source,
        )

    def _amount(self, payload):

        return self._positive_float(payload.get("amount"))

    def _positive_float(self, value):

        try:
            amount = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Enter a valid numeric amount."
            ) from exc

        if amount <= 0:
            raise ValueError(
                "Amount must be greater than zero."
            )

        return amount

    def _row_dict(self, row):

        return {
            key: row[key]
            for key in row.keys()
        }


APP_STATE = WebCommandCenter()


class RogueCircuitRequestHandler(BaseHTTPRequestHandler):

    server_version = "RogueCircuitQuant/1.0"

    def do_GET(self):

        parsed = urlparse(self.path)

        if parsed.path == "/api/state":
            self._send_json(APP_STATE.state())
            return

        self._send_static(parsed.path)

    def do_HEAD(self):

        parsed = urlparse(self.path)

        if parsed.path == "/api/state":
            self._send_head(
                "application/json",
                HTTPStatus.OK,
            )
            return

        self._send_static(
            parsed.path,
            include_body=False,
        )

    def do_POST(self):

        parsed = urlparse(self.path)
        payload = self._read_json()

        try:
            if parsed.path == "/api/deposits":
                data = APP_STATE.add_deposit(payload)
            elif parsed.path == "/api/withdrawals":
                data = APP_STATE.add_withdrawal(payload)
            elif parsed.path == "/api/snapshots/manual":
                data = APP_STATE.record_manual_snapshot(payload)
            elif parsed.path == "/api/snapshots/kraken":
                data = APP_STATE.record_kraken_snapshot()
            elif parsed.path == "/api/settings":
                data = APP_STATE.apply_settings(payload)
            elif parsed.path == "/api/trading/run-once":
                data = APP_STATE.run_one_cycle_response()
            elif parsed.path == "/api/bot/start":
                data = APP_STATE.start_service()
            elif parsed.path == "/api/bot/stop":
                data = APP_STATE.stop_service()
            elif parsed.path == "/api/emergency-stop":
                data = APP_STATE.emergency_stop()
            elif parsed.path == "/api/resume":
                data = APP_STATE.resume()
            else:
                self._send_json(
                    {"error": "Not found."},
                    HTTPStatus.NOT_FOUND,
                )
                return
        except Exception as exc:
            self._send_json(
                {"error": str(exc)},
                HTTPStatus.BAD_REQUEST,
            )
            return

        self._send_json(data)

    def log_message(self, format, *args):

        return

    def _send_static(
        self,
        path: str,
        include_body: bool = True,
    ):

        if path in {"", "/"}:
            file_path = WEB_ROOT / "index.html"
        else:
            clean_path = path.lstrip("/")
            file_path = (WEB_ROOT / clean_path).resolve()

            if WEB_ROOT.resolve() not in file_path.parents:
                self._send_json(
                    {"error": "Not found."},
                    HTTPStatus.NOT_FOUND,
                )
                return

        if not file_path.exists() or not file_path.is_file():
            self._send_json(
                {"error": "Not found."},
                HTTPStatus.NOT_FOUND,
            )
            return

        content_type = (
            mimetypes.guess_type(file_path.name)[0]
            or "application/octet-stream"
        )

        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        if include_body:
            self.wfile.write(body)

    def _send_head(
        self,
        content_type: str,
        status=HTTPStatus.OK,
    ):

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_json(self):

        length = int(self.headers.get("Content-Length", "0"))

        if length == 0:
            return {}

        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_json(
        self,
        data,
        status=HTTPStatus.OK,
    ):

        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host="127.0.0.1", port=8765):

    server = ThreadingHTTPServer(
        (host, port),
        RogueCircuitRequestHandler,
    )
    print(f"Rogue Circuit Quant browser app: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
