import json
import mimetypes
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import RLock, Timer
from urllib.parse import urlparse

from accounting.ledger import InvestmentLedger
from accounting.valuation import KrakenBalanceValuator
from analytics.chart_data import ChartDataBuilder
from config import (
    ALLOW_LIVE_TRADING,
    APP_AUTH_TOKEN,
    APP_DEPLOYMENT_MODE,
    CREDENTIAL_VAULT_KEY_PATH,
    CREDENTIAL_VAULT_PATH,
    LEDGER_DB_PATH,
    LIVE_LOOP_SECONDS,
    LIVE_CANDIDATE_MIN_AVERAGE_RETURN,
    LIVE_CANDIDATE_EVIDENCE_WINDOW,
    LIVE_CANDIDATE_MIN_PROFITABLE_RATE,
    LIVE_CANDIDATE_MIN_SHADOW_SAMPLES,
    LIVE_CANDIDATE_MIN_VALID_RATE,
    MAX_OPEN_POSITIONS,
    MAX_PORTFOLIO_EXPOSURE,
    MAX_ASSET_EXPOSURE,
    MIN_CASH_RESERVE,
    MAX_ORDER_NOTIONAL,
    MIN_SIGNAL_CONFIDENCE,
    NOTIFICATION_EMAIL_TO,
    NOTIFICATION_WEBHOOK_URL,
    PAPER_VALIDATION_MAX_DRAWDOWN,
    PAPER_VALIDATION_MIN_CLOSED_TRADES,
    PAPER_VALIDATION_MIN_CYCLES,
    PAPER_VALIDATION_MIN_GROWTH,
    PAPER_VALIDATION_MIN_OPPORTUNITY_RATE,
    SHADOW_VALIDATION_MAX_COST_RATE,
    SHADOW_VALIDATION_MIN_AVERAGE_RETURN,
    SHADOW_VALIDATION_MIN_PROFITABLE_RATE,
    SHADOW_VALIDATION_MIN_SAMPLES,
    SHADOW_VALIDATION_MIN_VALID_RATE,
    SHADOW_VALIDATION_WINDOW,
    PORTFOLIO_ALERT_PERCENT,
    TARGET_ASSET,
    TARGET_SYMBOL,
)
from exchange.client import KrakenClient
from live.bot_service import TradingBotService
from live.daily_scheduler import DailyPaperScheduler
from live.candidate_readiness import LiveCandidateEvaluator
from live.market_selection import DiversifiedMarketSelector
from live.market_health import MarketHealthEngine
from live.paper_validation import (
    PaperTradingValidator,
    PaperValidationConfig,
)
from live.paper_runtime import PaperRuntimeState
from live.shadow_validation import (
    ShadowTradingValidator,
    ShadowValidationConfig,
)
from live.trader import AutomatedKrakenTrader
from models.constants import BUY, HOLD, SELL
from live.execution_safety import (
    EXECUTION_MODES,
    LIMITED_LIVE,
    PAPER,
    SHADOW,
)
from notifications.channels import NotificationRouter
from security.auth import TokenAuth
from security.credentials import CredentialVault
from security.deployment import resolve_mode


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
REAL_ACCOUNT_SOURCES = ("kraken",)


class WebCommandCenter:

    def __init__(
        self,
        ledger_path=LEDGER_DB_PATH,
        credential_vault_path=CREDENTIAL_VAULT_PATH,
        credential_key_path=CREDENTIAL_VAULT_KEY_PATH,
    ):

        self.lock = RLock()
        self.trading_lock = RLock()
        self.ledger = InvestmentLedger(ledger_path)
        self.auth = TokenAuth(APP_AUTH_TOKEN)
        self.deployment_mode = resolve_mode(APP_DEPLOYMENT_MODE)
        self.credential_vault = CredentialVault(
            credential_vault_path,
            credential_key_path,
        )
        self.notifications = NotificationRouter(
            NOTIFICATION_WEBHOOK_URL,
            NOTIFICATION_EMAIL_TO,
        )
        self.chart_builder = ChartDataBuilder()
        self._notified_opportunities = set()
        self._last_target_asset_status = None
        self.market_opportunities = []
        self.market_selector = DiversifiedMarketSelector()
        self.market_health_engine = MarketHealthEngine()
        self.live_candidate_evaluator = LiveCandidateEvaluator(
            min_shadow_samples=LIVE_CANDIDATE_MIN_SHADOW_SAMPLES,
            min_valid_rate=LIVE_CANDIDATE_MIN_VALID_RATE,
            min_profitable_rate=LIVE_CANDIDATE_MIN_PROFITABLE_RATE,
            min_average_net_return=LIVE_CANDIDATE_MIN_AVERAGE_RETURN,
            evidence_window=LIVE_CANDIDATE_EVIDENCE_WINDOW,
        )
        self.kraken_permission_status = {
            "checked": False,
            "safe_for_live": False,
            "permissions": [],
            "missing": [],
            "forbidden": [],
            "message": "Run Test Connection to inspect API permissions.",
        }
        self.client = self._build_kraken_client()
        self.valuator = KrakenBalanceValuator(self.client)
        self.trader = AutomatedKrakenTrader(
            client=self.client,
        )
        self.paper_events = []
        self.paper_runtime = PaperRuntimeState()
        self.paper_evidence = self.paper_runtime.empty_evidence()
        self.paper_runtime_restored = False
        self._scheduled_session_phase = ""
        self._scheduled_cancel_generation = 0
        self._shadow_followup_timer = None
        self.paper_validator = PaperTradingValidator(
            PaperValidationConfig(
                min_cycles=PAPER_VALIDATION_MIN_CYCLES,
                min_closed_trades=PAPER_VALIDATION_MIN_CLOSED_TRADES,
                max_drawdown=PAPER_VALIDATION_MAX_DRAWDOWN,
                min_growth=PAPER_VALIDATION_MIN_GROWTH,
                min_opportunity_rate=(
                    PAPER_VALIDATION_MIN_OPPORTUNITY_RATE
                ),
            )
        )
        self.shadow_validator = ShadowTradingValidator(
            ShadowValidationConfig(
                min_samples=SHADOW_VALIDATION_MIN_SAMPLES,
                min_valid_rate=SHADOW_VALIDATION_MIN_VALID_RATE,
                min_profitable_rate=SHADOW_VALIDATION_MIN_PROFITABLE_RATE,
                max_cost_rate=SHADOW_VALIDATION_MAX_COST_RATE,
                min_average_net_return=SHADOW_VALIDATION_MIN_AVERAGE_RETURN,
                evidence_window=SHADOW_VALIDATION_WINDOW,
            )
        )
        self._restore_paper_runtime()
        self._load_controls()
        self.service = TradingBotService(
            cycle_runner=self.run_one_cycle,
            loop_seconds=self.trader.loop_seconds,
            on_success=self._service_success,
            on_error=self._service_error,
            on_stop=self._service_stopped,
        )
        self.trader.stop_requested = self.service.stop_requested
        self.daily_scheduler = DailyPaperScheduler(
            run_session=self._start_daily_paper_session,
            settings_loader=self._daily_schedule_settings,
        )
        self.daily_scheduler.start(initial_delay_seconds=5)
        pending_shadow = int(self.ledger.get_setting(
            "pending_shadow_cycles", "0"
        ))
        if pending_shadow > 0:
            self._schedule_shadow_followup(pending_shadow)

    def state(self):

        with self.lock:
            summary = asdict(self.ledger.summary(
                snapshot_sources=REAL_ACCOUNT_SOURCES,
            ))
            controls = asdict(
                self.ledger.bot_controls(
                    max_order_notional=self.trader.max_order_notional,
                    min_signal_confidence=(
                        self.trader.min_signal_confidence
                    ),
                    loop_seconds=self.trader.loop_seconds,
                )
            )

            target_asset = self.target_asset_status()
            market_health = self._market_health()
            live_candidates = self._live_candidates(market_health)

            return {
                "summary": summary,
                "controls": controls,
                "service": {
                    **self.service.status(),
                    "emergency_stop": self.trader.kill_switch.active(),
                    "symbols": self.trader.symbols,
                },
                "daily_schedule": self.daily_scheduler.status(),
                "market_opportunities": self.market_opportunities,
                "market_health": [
                    profile.as_dict()
                    for profile in market_health.values()
                ],
                "live_candidates": [
                    report.as_dict() for report in live_candidates
                ],
                "execution_safety": {
                    "mode": self.trader.mode,
                    "available_modes": sorted(EXECUTION_MODES),
                    "live_orders_enabled": ALLOW_LIVE_TRADING,
                    "permissions": self.kraken_permission_status,
                    "order_previews": self.trader.last_order_previews,
                },
                "allocation": self._allocation_status(),
                "paper_runtime": self._paper_runtime_status(),
                "auth": self.auth.status(),
                "deployment_mode": asdict(self.deployment_mode),
                "credential_status": self.credential_vault.status(),
                "target_asset": target_asset,
                "live_readiness": self.live_readiness(target_asset),
                "notification_channels": (
                    self.notifications.configured_channels()
                ),
                "chart_data": self.chart_builder.build(
                    self.ledger,
                    snapshot_sources=REAL_ACCOUNT_SOURCES,
                ),
                "snapshots": [
                    asdict(snapshot)
                    for snapshot in self.ledger.snapshots(
                        sources=REAL_ACCOUNT_SOURCES,
                    )
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
                "audit_log": [
                    self._row_dict(row)
                    for row in self.ledger.audit_log()
                ],
                "paper_live": [
                    self._row_dict(row)
                    for row in self.ledger.paper_live_comparisons()
                ],
                "shadow_observations": [
                    self._row_dict(row)
                    for row in self.ledger.shadow_observations(limit=100)
                ],
            }

    def add_deposit(self, payload):

        self._assert_writable()
        amount = self._amount(payload)
        note = payload.get("note", "")

        with self.lock:
            self.ledger.add_deposit(amount, note)
            self._audit(
                "deposit_added",
                f"Deposit recorded for ${amount:.2f}.",
            )

        return self.state()

    def add_withdrawal(self, payload):

        self._assert_writable()
        amount = self._amount(payload)
        note = payload.get("note", "")

        with self.lock:
            self.ledger.add_withdrawal(amount, note)
            self._audit(
                "withdrawal_added",
                f"Withdrawal recorded for ${amount:.2f}.",
            )

        return self.state()

    def record_manual_snapshot(self, payload):

        self._assert_writable()
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
            self._audit(
                "manual_snapshot_recorded",
                f"Manual portfolio value set to ${total_value:.2f}.",
            )

        return self.state()

    def record_kraken_snapshot(self):

        self._assert_writable()
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
            self._audit(
                "kraken_snapshot_recorded",
                f"Kraken value refreshed at ${valuation.total_value:.2f}.",
            )

        return self.state()

    def check_kraken_connection(self):

        self._assert_writable()

        with self.lock:
            status = self.target_asset_status(refresh=True)
            self.kraken_permission_status = (
                self.trader.execution_safety
                .inspect_permissions(self.client)
                .as_dict()
            )
            self._last_target_asset_status = status
            level = "INFO" if status["ready_for_paper"] else "WARN"
            self.ledger.add_alert(
                level,
                status["message"],
                "kraken_connection",
            )
            self._audit(
                "kraken_connection_checked",
                status["message"],
                source="kraken_connection",
            )

        state = self.state()
        state["message"] = status["message"]
        return state

    def set_execution_mode(self, payload):

        self._assert_writable()
        requested = str(payload.get("mode", "")).lower()

        if requested not in EXECUTION_MODES:
            raise ValueError("Choose paper, shadow, or limited live mode.")

        if requested in {SHADOW, LIMITED_LIVE}:
            if not self.credential_vault.status()["kraken_configured"]:
                raise RuntimeError(
                    "Kraken credentials are required for this mode."
                )

        if requested == LIMITED_LIVE:
            confirmation = str(payload.get("confirmation", ""))
            readiness = self.live_readiness()
            if confirmation != "ENABLE LIMITED LIVE":
                raise RuntimeError(
                    "Limited live mode requires the exact confirmation phrase."
                )
            if not readiness["ready"]:
                raise RuntimeError(
                    "Limited live mode is locked: "
                    + " ".join(readiness["reasons"])
                )
            eligible_symbols = {
                item["symbol"]
                for item in readiness["candidate_validation"]
                if item["eligible"]
            }
        else:
            eligible_symbols = set()

        self.service.stop(wait=True)
        with self.lock:
            self.trader.set_execution_mode(requested)
            self.trader.live_symbol_allowlist = eligible_symbols
            self.ledger.set_setting("execution_mode", requested)
            self._audit(
                "execution_mode_changed",
                f"Execution mode changed to {requested}.",
                source="execution_safety",
            )

        state = self.state()
        state["message"] = f"Execution mode set to {requested}."
        return state

    def use_target_symbol(self):

        self._assert_writable()

        with self.lock:
            status = self.target_asset_status(refresh=True)
            self._last_target_asset_status = status

            if not status["market_available"]:
                raise RuntimeError(status["message"])

            self.trader.symbols = [TARGET_SYMBOL]
            self.ledger.set_setting(
                "live_symbols",
                TARGET_SYMBOL,
            )
            self.ledger.add_alert(
                "INFO",
                f"Trading bot symbol set to {TARGET_SYMBOL}.",
                "kraken_connection",
            )
            self._audit(
                "target_symbol_enabled",
                f"Trading bot symbol set to {TARGET_SYMBOL}.",
                source="kraken_connection",
            )

            status["configured_for_bot"] = True
            status["ready_for_paper"] = (
                status["market_available"]
                and status["balance"] > 0
            )
            status["ready_for_live"] = (
                status["ready_for_paper"]
                and self.deployment_mode.live_trading_allowed
            )
            status["message"] = (
                f"{TARGET_SYMBOL} is selected for the bot. "
                "Keep paper mode on until validation looks good."
            )
            self._last_target_asset_status = status

        state = self.state()
        state["message"] = (
            f"Bot is now configured for {TARGET_SYMBOL}. "
            "Keep paper mode on until validation looks good."
        )
        return state

    def scan_market_opportunities(self, payload):

        self._assert_writable()
        scan_limit = int(payload.get("scan_limit", 8))
        active_limit = int(payload.get("active_limit", 3))
        auto_shadow = bool(payload.get("auto_shadow", True))
        shadow_cycles = int(payload.get("shadow_cycles", 3))

        if not 2 <= scan_limit <= 12:
            raise ValueError("Scan limit must be between 2 and 12.")

        if not 1 <= active_limit <= 5:
            raise ValueError("Active market limit must be between 1 and 5.")

        opportunities, selected = self._perform_market_scan(
            scan_limit,
            active_limit,
        )

        state = self.state()
        state["message"] = (
            f"Market scan complete. Paper bot now tracks "
            f"{', '.join(selected)}. Rankings are estimates, not "
            "guaranteed profit."
        )
        return state

    def apply_settings(self, payload):

        self._assert_writable()
        max_order = self._positive_float(
            payload.get("max_order_notional")
        )
        min_confidence = float(payload.get("min_signal_confidence"))
        loop_seconds = self._positive_float(
            payload.get("loop_seconds")
        )
        max_open_positions = int(payload.get(
            "max_open_positions",
            self.trader.allocator.max_open_positions,
        ))
        max_portfolio_exposure = float(payload.get(
            "max_portfolio_exposure",
            self.trader.allocator.max_portfolio_exposure,
        ))
        max_asset_exposure = float(payload.get(
            "max_asset_exposure",
            self.trader.allocator.max_asset_exposure,
        ))
        min_cash_reserve = float(payload.get(
            "min_cash_reserve",
            self.trader.allocator.min_cash_reserve,
        ))

        if not 0 <= min_confidence <= 1:
            raise ValueError(
                "Minimum confidence must be between 0 and 1."
            )
        if not 1 <= max_open_positions <= 10:
            raise ValueError("Open market limit must be between 1 and 10.")
        if not 0 < max_asset_exposure <= max_portfolio_exposure <= 1:
            raise ValueError(
                "Asset exposure must be positive and no higher than total exposure."
            )
        if not 0 <= min_cash_reserve < 1:
            raise ValueError("Cash reserve must be between 0 and 99 percent.")

        with self.lock:
            self.trader.max_order_notional = max_order
            self.trader.min_signal_confidence = min_confidence
            self.trader.loop_seconds = loop_seconds
            self.service.loop_seconds = loop_seconds
            self.trader.allocator.max_open_positions = max_open_positions
            self.trader.allocator.max_portfolio_exposure = max_portfolio_exposure
            self.trader.allocator.max_asset_exposure = max_asset_exposure
            self.trader.allocator.min_cash_reserve = min_cash_reserve
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
            self.ledger.set_setting("max_open_positions", max_open_positions)
            self.ledger.set_setting(
                "max_portfolio_exposure", max_portfolio_exposure
            )
            self.ledger.set_setting("max_asset_exposure", max_asset_exposure)
            self.ledger.set_setting("min_cash_reserve", min_cash_reserve)
            self.ledger.add_alert(
                "INFO",
                "Browser risk controls updated.",
                "browser",
            )
            self._audit(
                "risk_controls_updated",
                (
                    f"max_order={max_order}, "
                    f"min_confidence={min_confidence}, "
                    f"loop_seconds={loop_seconds}"
                    f", max_open_positions={max_open_positions}, "
                    f"portfolio_exposure={max_portfolio_exposure}, "
                    f"asset_exposure={max_asset_exposure}, "
                    f"cash_reserve={min_cash_reserve}"
                ),
            )

        return self.state()

    def apply_daily_schedule(self, payload):
        self._assert_writable()
        enabled = bool(payload.get("enabled"))
        schedule_time = str(payload.get("time", "09:00")).strip()
        cycles = int(payload.get("cycles", 12))
        auto_scan = bool(payload.get("auto_scan", True))
        scan_limit = int(payload.get("scan_limit", 8))
        active_limit = int(payload.get("active_limit", 3))
        auto_shadow = bool(payload.get("auto_shadow", True))
        shadow_cycles = int(payload.get("shadow_cycles", 3))

        try:
            hour, minute = (int(value) for value in schedule_time.split(":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Choose a valid daily start time.") from exc
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Choose a valid daily start time.")
        if not 1 <= cycles <= 288:
            raise ValueError("Daily cycles must be between 1 and 288.")
        if not 2 <= scan_limit <= 12:
            raise ValueError("Scan limit must be between 2 and 12.")
        if not 1 <= active_limit <= 5 or active_limit > scan_limit:
            raise ValueError("Active markets must be between 1 and 5.")
        if not 1 <= shadow_cycles <= 24:
            raise ValueError("Shadow cycles must be between 1 and 24.")

        normalized_time = f"{hour:02d}:{minute:02d}"
        with self.lock:
            self.ledger.set_setting("daily_paper_enabled", int(enabled))
            self.ledger.set_setting("daily_paper_time", normalized_time)
            self.ledger.set_setting("daily_paper_cycles", cycles)
            self.ledger.set_setting("daily_paper_auto_scan", int(auto_scan))
            self.ledger.set_setting("daily_paper_scan_limit", scan_limit)
            self.ledger.set_setting("daily_paper_active_limit", active_limit)
            self.ledger.set_setting("daily_auto_shadow", int(auto_shadow))
            self.ledger.set_setting("daily_shadow_cycles", shadow_cycles)
            self._audit(
                "daily_paper_schedule_updated",
                (
                    f"enabled={enabled}, time={normalized_time}, cycles={cycles}, "
                    f"auto_scan={auto_scan}, markets={active_limit}, "
                    f"auto_shadow={auto_shadow}, shadow_cycles={shadow_cycles}"
                ),
                source="daily_scheduler",
            )

        state = self.state()
        state["message"] = (
            f"Daily paper session scheduled for {normalized_time}."
            if enabled
            else "Daily paper schedule disabled."
        )
        return state

    def _daily_schedule_settings(self):
        return {
            "enabled": self.ledger.get_setting(
                "daily_paper_enabled", "0"
            ) == "1",
            "time": self.ledger.get_setting("daily_paper_time", "09:00"),
            "cycles": int(self.ledger.get_setting("daily_paper_cycles", "12")),
            "auto_scan": self.ledger.get_setting(
                "daily_paper_auto_scan", "1"
            ) == "1",
            "scan_limit": int(self.ledger.get_setting(
                "daily_paper_scan_limit", "8"
            )),
            "active_limit": int(self.ledger.get_setting(
                "daily_paper_active_limit", "3"
            )),
            "auto_shadow": self.ledger.get_setting(
                "daily_auto_shadow", "1"
            ) == "1",
            "shadow_cycles": int(self.ledger.get_setting(
                "daily_shadow_cycles", "3"
            )),
            "last_run_date": self.ledger.get_setting(
                "daily_paper_last_run_date", ""
            ),
        }

    def _start_daily_paper_session(self, cycles: int, run_date: str):
        with self.lock:
            cancel_generation = self._scheduled_cancel_generation
        settings = self._daily_schedule_settings()
        scan_message = ""
        if settings["auto_scan"]:
            try:
                _, selected = self._perform_market_scan(
                    settings["scan_limit"],
                    settings["active_limit"],
                )
                scan_message = f" Selected {', '.join(selected)}."
            except Exception as exc:
                scan_message = f" Market refresh failed: {exc}"

        with self.lock:
            if cancel_generation != self._scheduled_cancel_generation:
                result = "Skipped because the scheduled session was stopped."
            elif self.trader.kill_switch.active():
                result = "Skipped because the emergency stop is active."
            elif self.service.is_running():
                result = "Skipped because a bot session is already running."
            else:
                self.trader.set_execution_mode(PAPER)
                self.trader.live_symbol_allowlist = set()
                self.ledger.set_setting("execution_mode", PAPER)
                started = self.service.start(max_cycles=cycles)
                if started and settings["auto_shadow"]:
                    self._scheduled_session_phase = "paper"
                    self.ledger.set_setting(
                        "pending_shadow_cycles",
                        settings["shadow_cycles"],
                    )
                result = (
                    f"Started a bounded paper session for {cycles} cycles."
                    f"{scan_message}"
                    if started
                    else "Skipped because a bot session is already running."
                )
            self.ledger.set_setting("daily_paper_last_run_date", run_date)
            self._audit(
                "daily_paper_session",
                result,
                source="daily_scheduler",
                actor="scheduler",
            )
            return result

    def _perform_market_scan(self, scan_limit: int, active_limit: int):
        candidates = self._market_scan_candidates(scan_limit)
        with self.trading_lock:
            opportunities = self.trader.scan_markets(candidates)
        if not opportunities:
            raise RuntimeError(
                "No Kraken markets produced enough data for analysis."
            )
        selection = self.market_selector.select(
            opportunities,
            active_limit,
            health_by_symbol=self._market_health(),
        )
        open_symbols = [
            trade.symbol for trade in self.trader.portfolio.open_trades
        ]
        selected = list(dict.fromkeys(
            open_symbols + list(selection.selected)
        ))[:max(active_limit, len(open_symbols))]
        if not selected:
            raise RuntimeError(
                "No crypto market passed the profitability and quality filters."
            )

        with self.lock:
            self.market_opportunities = [asdict(item) for item in opportunities]
            self.trader.symbols = selected
            self.ledger.set_setting("live_symbols", ",".join(selected))
            self.ledger.add_alert(
                "INFO",
                f"Paper bot market set updated: {', '.join(selected)}.",
                "market_scanner",
            )
            self._audit(
                "market_scan_completed",
                f"Analyzed {len(opportunities)} market(s); selected "
                f"{', '.join(selected)} for paper trading.",
                source="market_scanner",
            )
        return opportunities, selected

    def _market_health(self):
        return self.market_health_engine.evaluate(
            self.ledger.shadow_observations(),
            self.ledger.trades(limit=500),
        )

    def _live_candidates(self, health_by_symbol=None):
        return self.live_candidate_evaluator.evaluate(
            self.trader.symbols,
            health_by_symbol or self._market_health(),
            self.ledger.shadow_observations(),
        )

    def _allocation_status(self):
        portfolio = self.trader.portfolio
        equity = float(portfolio.account_value())
        invested = float(portfolio.position_value())
        return {
            "open_positions": portfolio.open_positions(),
            "max_open_positions": self.trader.allocator.max_open_positions,
            "invested": invested,
            "cash": float(portfolio.cash),
            "exposure": invested / equity if equity else 0.0,
            "max_portfolio_exposure": (
                self.trader.allocator.max_portfolio_exposure
            ),
            "max_asset_exposure": self.trader.allocator.max_asset_exposure,
            "min_cash_reserve": self.trader.allocator.min_cash_reserve,
            "decisions": self.trader.last_allocation_decisions,
        }

    def run_one_cycle(self):

        self._assert_writable()
        self._assert_trading_allowed()

        # Market downloads and optimization can be slow. Keep them outside the
        # dashboard lock so status, stop, and emergency controls stay responsive.
        with self.trading_lock:
            events = self.trader.run_once()

        with self.lock:
            self.paper_events.extend(events)
            if self.trader.mode == PAPER:
                expected = set(self.trader.symbols)
                qualified = (
                    not self.trader.last_cycle_note
                    and bool(expected)
                    and len(events) == len(expected)
                    and {event.symbol for event in events} == expected
                    and all(
                        event.price > 0
                        and event.action in {BUY, SELL, HOLD}
                        and event.strategy not in {"MarketError", "KillSwitch"}
                        for event in events
                    )
                )
                if qualified:
                    self.paper_evidence["cycles"] += 1
                    self.paper_evidence["total_events"] += len(events)
                    self.paper_evidence["executed_events"] += sum(
                        1 for event in events if event.executed
                    )
                    self.paper_evidence["opportunity_events"] += sum(
                        1 for event in events if event.opportunity
                    )
                else:
                    self.paper_evidence["unverified_cycles"] += 1
                    self.ledger.add_alert(
                        "WARN",
                        "Paper run did not qualify for readiness: "
                        "one or more selected markets lacked a fresh signal.",
                        "paper_validation",
                    )
            if self.trader.mode == LIMITED_LIVE:
                valuation = self.valuator.snapshot()
                portfolio_value = valuation.total_value
                position_value = valuation.positions_value
                cash_value = valuation.cash_value
                snapshot_source = "kraken"
            else:
                portfolio_value = self.trader.portfolio.account_value()
                position_value = self.trader.portfolio.position_value()
                cash_value = self.trader.portfolio.cash
                snapshot_source = f"browser_{self.trader.mode}_trader"

            self.ledger.record_snapshot(
                total_value=portfolio_value,
                cash_value=cash_value,
                positions_value=position_value,
                source=snapshot_source,
            )
            self._record_value_alerts(portfolio_value, snapshot_source)

            for event in events:
                if self.trader.mode == SHADOW and event.price > 0:
                    self.ledger.resolve_shadow_observations(
                        event.symbol,
                        event.price,
                    )
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
                if self.trader.mode == LIMITED_LIVE and event.executed:
                    live_action = event.action
                elif self.trader.mode == SHADOW:
                    live_action = "SHADOW"
                else:
                    live_action = "LOCKED"
                self.ledger.record_paper_live_comparison(
                    symbol=event.symbol,
                    paper_action=event.action,
                    live_action=live_action,
                    paper_price=event.price,
                    live_price=event.price,
                    difference=0.0,
                    reason=event.reason,
                )

                if (
                    self.trader.mode == SHADOW
                    and event.action == BUY
                    and event.order_id
                ):
                    preview = self.trader.last_order_previews.get(
                        event.symbol,
                        {},
                    )
                    notional = float(preview.get("notional") or 0.0)
                    costs = (
                        float(preview.get("estimated_fee") or 0.0)
                        + float(preview.get("estimated_slippage") or 0.0)
                    )
                    self.ledger.record_shadow_observation(
                        symbol=event.symbol,
                        action=event.action,
                        strategy=event.strategy,
                        confidence=event.confidence,
                        entry_price=event.price,
                        quantity=event.quantity,
                        valid=bool(preview.get("valid")),
                        cost_rate=costs / notional if notional else 0.0,
                        reason=event.reason,
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

                if event.opportunity:
                    self._record_opportunity_alert(event)

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
                    symbol=trade.symbol,
                    side="SELL",
                    quantity=trade.quantity,
                    price=trade.exit_price,
                    pnl=trade.pnl,
                    source=trade.strategy,
                )
                trade._web_ledger_recorded = True

            self._audit(
                "trading_cycle_completed",
                f"Cycle completed with {len(events)} event(s).",
                source="browser_trader",
            )
            if self.trader.last_cycle_note:
                self.ledger.add_alert(
                    "WARN",
                    self.trader.last_cycle_note,
                    "browser_trader",
                )
            if self.trader.mode == PAPER:
                self._save_paper_runtime()

        message = f"Trading cycle completed with {len(events)} event(s)."
        if self.trader.last_cycle_note:
            message += f" {self.trader.last_cycle_note}"
        return message

    def run_one_cycle_response(self):

        message = self.run_one_cycle()
        state = self.state()
        state["message"] = message
        return state

    def live_readiness(
        self,
        target_asset: dict | None = None,
    ):

        target_asset = target_asset or self.target_asset_status()
        validation = self.paper_validator.evaluate(
            portfolio=self.trader.portfolio,
            events=self.paper_events,
            cycles=self.paper_evidence["cycles"],
            evidence=self.paper_evidence,
        )
        shadow_validation = self.shadow_validator.evaluate(
            self.ledger.shadow_observations()
        )
        candidate_reports = self._live_candidates()
        eligible_candidates = [
            report for report in candidate_reports if report.eligible
        ]
        reasons = list(validation.reasons)
        reasons.extend(shadow_validation.reasons)
        credentials_configured = self.credential_vault.status()[
            "kraken_configured"
        ]
        emergency_stop_clear = not self.trader.kill_switch.active()

        if not credentials_configured:
            reasons.append("Kraken credentials are not configured.")

        if not eligible_candidates:
            reasons.append(
                "No selected market has passed the per-market promotion gate."
            )

        if not self.deployment_mode.live_trading_allowed:
            reasons.append("Deployment mode does not allow live trading.")

        permissions_safe = self.kraken_permission_status["safe_for_live"]
        if not permissions_safe:
            reasons.append(self.kraken_permission_status["message"])

        if not ALLOW_LIVE_TRADING:
            reasons.append("Live order submission is disabled by configuration.")

        if not emergency_stop_clear:
            reasons.append("Emergency stop is active.")

        ready = not reasons

        return {
            "ready": ready,
            "mode": self.deployment_mode.name,
            "deployment_allows_live": (
                self.deployment_mode.live_trading_allowed
            ),
            "credentials_configured": credentials_configured,
            "permissions_safe": permissions_safe,
            "live_orders_enabled": ALLOW_LIVE_TRADING,
            "target_ready_for_paper": target_asset["ready_for_paper"],
            "eligible_candidate_count": len(eligible_candidates),
            "candidate_validation": [
                report.as_dict() for report in candidate_reports
            ],
            "emergency_stop_clear": emergency_stop_clear,
            "paper_validation": asdict(validation),
            "shadow_validation": asdict(shadow_validation),
            "reasons": reasons,
            "message": (
                "Live deployment gates are satisfied."
                if ready
                else "Live deployment remains locked."
            ),
        }

    def start_service(self):

        self._assert_writable()
        self._assert_trading_allowed()

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
            self._audit(
                "bot_service_started",
                "Background trading service start requested.",
            )

        return self.state()

    def stop_service(self):

        self._assert_writable()
        with self.lock:
            self._scheduled_cancel_generation += 1
        self._cancel_shadow_followup()
        self.service.stop()

        with self.lock:
            self.ledger.add_alert(
                "INFO",
                "Browser bot service stop requested.",
                "browser",
            )
            self._audit(
                "bot_service_stopped",
                "Background trading service stop requested.",
            )

        return self.state()

    def emergency_stop(self):

        self._assert_writable()
        with self.lock:
            self._scheduled_cancel_generation += 1
        self._cancel_shadow_followup()
        self.service.stop()

        canceled_orders = False
        if self.trader.mode == LIMITED_LIVE:
            try:
                self.client.cancel_all_orders()
                canceled_orders = True
            except Exception as exc:
                with self.lock:
                    self.ledger.add_alert(
                        "ERROR",
                        f"Emergency order cancellation failed: {exc}",
                        "execution_safety",
                    )

        with self.lock:
            self.trader.emergency_stop()
            self.ledger.set_emergency_stop(True)
            self.ledger.add_alert(
                "CRITICAL",
                "Browser emergency stop activated.",
                "browser",
            )
            self._notify(
                "CRITICAL",
                "Browser emergency stop activated.",
                "browser",
            )
            self._audit(
                "emergency_stop",
                (
                    "Trading stopped by browser command center. "
                    f"Kraken orders canceled={canceled_orders}."
                ),
            )

        return self.state()

    def resume(self):

        self._assert_writable()
        with self.lock:
            self.trader.resume_trading()
            self.ledger.set_emergency_stop(False)
            self.ledger.add_alert(
                "INFO",
                "Browser trading resumed from emergency stop.",
                "browser",
            )
            self._audit(
                "trading_resumed",
                "Emergency stop cleared by browser command center.",
            )

        return self.state()

    def store_credentials(self, payload):

        self._assert_writable()
        api_key = str(payload.get("api_key", "")).strip()
        api_secret = str(payload.get("api_secret", "")).strip()

        with self.lock:
            self.credential_vault.store_kraken_credentials(
                api_key,
                api_secret,
            )
            self._reload_kraken_client()
            self.kraken_permission_status = {
                "checked": False,
                "safe_for_live": False,
                "permissions": [],
                "missing": [],
                "forbidden": [],
                "message": "Run Test Connection to inspect API permissions.",
            }
            self.ledger.add_alert(
                "INFO",
                "Encrypted Kraken credentials updated.",
                "browser",
            )
            self._audit(
                "kraken_credentials_updated",
                "Encrypted Kraken credential vault was updated.",
            )

        state = self.state()
        state["message"] = "Kraken credentials encrypted and stored."
        return state

    def target_asset_status(
        self,
        refresh: bool = False,
    ):

        credentials_configured = self.credential_vault.status()[
            "kraken_configured"
        ]
        status = {
            "asset": TARGET_ASSET,
            "symbol": TARGET_SYMBOL,
            "credentials_configured": credentials_configured,
            "market_available": False,
            "configured_for_bot": TARGET_SYMBOL in self.trader.symbols,
            "balance": 0.0,
            "estimated_usd": 0.0,
            "ready_for_paper": False,
            "ready_for_live": False,
            "message": (
                "Store Kraken API credentials before checking the "
                f"{TARGET_ASSET} balance."
            ),
        }

        if not credentials_configured:
            return status

        if not refresh:
            if self._last_target_asset_status is not None:
                return self._last_target_asset_status

            status["message"] = (
                "Kraken credentials are stored. Run the Kraken/QUID "
                "check to validate balance and market availability."
            )
            return status

        try:
            market_available = self.client.has_market(TARGET_SYMBOL)
        except Exception as exc:
            status["message"] = (
                f"Could not load Kraken markets for {TARGET_SYMBOL}: {exc}"
            )
            return status

        status["market_available"] = market_available
        status["configured_for_bot"] = TARGET_SYMBOL in self.trader.symbols

        try:
            balance = self.client.fetch_balance()
        except Exception as exc:
            status["message"] = f"Could not fetch Kraken balance: {exc}"
            return status

        asset_balance = self._balance_amount(
            balance,
            TARGET_ASSET,
        )
        status["balance"] = asset_balance

        if market_available and asset_balance > 0:
            try:
                ticker = self.client.fetch_ticker(TARGET_SYMBOL)
                price = ticker.get("last") or ticker.get("close")
                status["estimated_usd"] = asset_balance * float(price)
            except Exception:
                status["estimated_usd"] = 0.0

        status["ready_for_paper"] = (
            market_available
            and asset_balance > 0
            and status["configured_for_bot"]
        )
        status["ready_for_live"] = (
            status["ready_for_paper"]
            and self.deployment_mode.live_trading_allowed
        )

        if not market_available:
            status["message"] = (
                f"{TARGET_SYMBOL} is not currently available as a "
                "direct Kraken Pro market. Automation is locked."
            )
        elif asset_balance <= 0:
            status["message"] = (
                f"No {TARGET_ASSET} balance was found on Kraken."
            )
        elif not status["configured_for_bot"]:
            status["message"] = (
                f"{TARGET_ASSET} balance found and {TARGET_SYMBOL} is "
                "tradable. Set the bot symbol to QUID before automation."
            )
        elif not self.deployment_mode.live_trading_allowed:
            status["message"] = (
                f"{TARGET_ASSET} balance found and {TARGET_SYMBOL} is "
                "tradable. Paper validation is ready; live mode remains "
                "locked by deployment settings."
            )
        else:
            status["message"] = (
                f"{TARGET_ASSET} balance found and {TARGET_SYMBOL} is "
                "tradable. Live deployment mode is enabled."
            )

        return status

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
        self.trader.allocator.max_open_positions = int(self.ledger.get_setting(
            "max_open_positions", str(MAX_OPEN_POSITIONS)
        ))
        self.trader.allocator.max_portfolio_exposure = float(
            self.ledger.get_setting(
                "max_portfolio_exposure", str(MAX_PORTFOLIO_EXPOSURE)
            )
        )
        self.trader.allocator.max_asset_exposure = float(
            self.ledger.get_setting(
                "max_asset_exposure", str(MAX_ASSET_EXPOSURE)
            )
        )
        self.trader.allocator.min_cash_reserve = float(
            self.ledger.get_setting("min_cash_reserve", str(MIN_CASH_RESERVE))
        )

        if controls.emergency_stop:
            self.trader.emergency_stop()

        symbols = self.ledger.get_setting("live_symbols", "")

        if symbols:
            self.trader.symbols = [
                symbol.strip()
                for symbol in symbols.split(",")
                if symbol.strip()
            ]

        execution_mode = self.ledger.get_setting("execution_mode", PAPER)
        if execution_mode == LIMITED_LIVE:
            execution_mode = PAPER
            self.ledger.set_setting("execution_mode", PAPER)
        if execution_mode in EXECUTION_MODES:
            self.trader.set_execution_mode(execution_mode)

    def _restore_paper_runtime(self):
        payload = self.ledger.get_json_setting("paper_runtime_state", {})
        evidence, restored = self.paper_runtime.restore(self.trader, payload)
        self.paper_evidence = evidence
        self.paper_runtime_restored = restored

    def _save_paper_runtime(self):
        payload = self.paper_runtime.export(
            self.trader,
            self.paper_evidence,
        )
        self.ledger.set_json_setting("paper_runtime_state", payload)
        self.paper_runtime_restored = True

    def _paper_runtime_status(self):
        payload = self.ledger.get_json_setting("paper_runtime_state", {}) or {}
        return {
            "restored": self.paper_runtime_restored,
            "updated_at": payload.get("updated_at", ""),
            "cycles": self.paper_evidence["cycles"],
            "open_positions": self.trader.portfolio.open_positions(),
            "closed_trades": len(self.trader.portfolio.closed_trades),
            **self.paper_evidence,
        }

    def _market_scan_candidates(self, limit: int) -> list[str]:

        markets = self.client.load_markets()
        eligible = {
            symbol
            for symbol, market in markets.items()
            if market.get("quote") in {"USD", "USDC", "USDT"}
            and market.get("spot", True)
            and market.get("active", True) is not False
            and not market.get("darkpool", False)
        }

        ranked = []
        try:
            tickers = self.client.fetch_tickers(list(eligible))
            ranked = sorted(
                eligible,
                key=lambda symbol: self._ticker_volume(
                    tickers.get(symbol, {})
                ),
                reverse=True,
            )
        except Exception:
            preferred = [
                TARGET_SYMBOL,
                "BTC/USD",
                "ETH/USD",
                "SOL/USD",
                "XRP/USD",
                "ADA/USD",
                "DOGE/USD",
                "DOT/USD",
                "LINK/USD",
                "LTC/USD",
                "AVAX/USD",
                "XLM/USD",
            ]
            ranked = [symbol for symbol in preferred if symbol in eligible]

        existing = [
            symbol for symbol in self.trader.symbols
            if symbol in eligible
        ]
        ordered = list(dict.fromkeys(existing + ranked))
        return ordered[:limit]

    @staticmethod
    def _ticker_volume(ticker: dict) -> float:

        for key in ("quoteVolume", "baseVolume"):
            try:
                value = float(ticker.get(key) or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0:
                return value
        return 0.0

    def _build_kraken_client(self):

        credentials = self.credential_vault.load_kraken_credentials()
        return KrakenClient.from_credentials(credentials)

    def _reload_kraken_client(self):

        self.client = self._build_kraken_client()
        self.valuator = KrakenBalanceValuator(self.client)
        self.trader.client = self.client

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
            self._notify(
                "ERROR",
                str(exc),
                "browser_service",
            )

    def _service_stopped(self):
        phase = self._scheduled_session_phase
        self._scheduled_session_phase = ""
        with self.lock:
            self.ledger.add_alert(
                "INFO",
                "Browser bot service stopped.",
                "browser_service",
            )
            if phase == "shadow":
                self.trader.set_execution_mode(PAPER)
                self.trader.live_symbol_allowlist = set()
                self.ledger.set_setting("execution_mode", PAPER)
                self.ledger.set_setting("pending_shadow_cycles", 0)
                self._audit(
                    "daily_shadow_completed",
                    "Scheduled shadow validation completed; returned to paper mode.",
                    source="daily_scheduler",
                    actor="scheduler",
                )
                return

        if phase == "paper":
            cycles = int(self.ledger.get_setting("pending_shadow_cycles", "0"))
            if cycles > 0:
                self._schedule_shadow_followup(cycles)

    def _schedule_shadow_followup(self, cycles: int):
        if self._shadow_followup_timer is not None:
            self._shadow_followup_timer.cancel()
        self._shadow_followup_timer = Timer(
            0.5,
            self._start_shadow_followup,
            args=(int(cycles),),
        )
        self._shadow_followup_timer.daemon = True
        self._shadow_followup_timer.start()

    def _start_shadow_followup(self, cycles: int):
        self._shadow_followup_timer = None
        if self.service.is_running():
            self._schedule_shadow_followup(cycles)
            return
        with self.lock:
            if self.trader.kill_switch.active():
                self._cancel_shadow_followup()
                return
            if not self.credential_vault.status()["kraken_configured"]:
                self.ledger.set_setting("pending_shadow_cycles", 0)
                self.trader.set_execution_mode(PAPER)
                self.ledger.set_setting("execution_mode", PAPER)
                self.ledger.add_alert(
                    "WARN",
                    "Scheduled shadow validation skipped: Kraken credentials missing.",
                    "daily_scheduler",
                )
                return
            self.trader.set_execution_mode(SHADOW)
            self.trader.live_symbol_allowlist = set()
            self.ledger.set_setting("execution_mode", SHADOW)
            self._scheduled_session_phase = "shadow"
            started = self.service.start(max_cycles=cycles)
            if not started:
                self._scheduled_session_phase = ""
                self.trader.set_execution_mode(PAPER)
                self.ledger.set_setting("execution_mode", PAPER)
                self._schedule_shadow_followup(cycles)
                return
            self._audit(
                "daily_shadow_started",
                f"Started scheduled no-order shadow validation for {cycles} cycles.",
                source="daily_scheduler",
                actor="scheduler",
            )

    def _cancel_shadow_followup(self):
        self._scheduled_session_phase = ""
        self.ledger.set_setting("pending_shadow_cycles", 0)
        if self._shadow_followup_timer is not None:
            self._shadow_followup_timer.cancel()
            self._shadow_followup_timer = None

    def _record_value_alerts(
        self,
        total_value: float,
        source: str,
    ):

        snapshots = self.ledger.snapshots(
            limit=2,
            sources=(source,),
        )

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
        self._notify(
            level,
            (
                f"Portfolio {direction} {abs(change_percent):.2%} "
                f"from previous snapshot."
            ),
            source,
        )

    def _record_opportunity_alert(self, event):

        key = (
            event.symbol,
            event.strategy,
            event.action,
        )

        if key in self._notified_opportunities:
            return

        self._notified_opportunities.add(key)
        message = (
            f"{event.symbol} opportunity: {event.action} signal "
            f"confidence={event.confidence:.2f} at ${event.price:,.2f}. "
            f"{event.opportunity_reason}"
        )
        self.ledger.add_alert(
            "OPPORTUNITY",
            message,
            "browser_trader",
        )
        self._notify(
            "OPPORTUNITY",
            message,
            "browser_trader",
        )

    def _assert_writable(self):

        if self.deployment_mode.name == "maintenance":
            raise RuntimeError(
                "Deployment mode is maintenance; write actions are disabled."
            )

    def _assert_trading_allowed(self):

        if (
            self.trader.mode == "live"
            and not self.deployment_mode.live_trading_allowed
        ):
            raise RuntimeError(
                "Live trading is locked by deployment mode."
            )

    def _audit(
        self,
        action: str,
        detail: str,
        source: str = "browser",
        actor: str = "local-user",
    ):

        self.ledger.record_audit_event(
            actor=actor,
            action=action,
            detail=detail,
            source=source,
        )

    def _notify(
        self,
        level: str,
        message: str,
        source: str,
    ):

        try:
            delivered = self.notifications.notify(
                level,
                message,
                source,
            )
        except Exception as exc:
            self.ledger.add_alert(
                "WARN",
                f"Notification delivery failed: {exc}",
                "notifications",
            )
            return

        if delivered:
            self.ledger.add_alert(
                "INFO",
                f"Notification delivered via {', '.join(delivered)}.",
                "notifications",
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

    def _balance_amount(
        self,
        balance,
        asset: str,
    ) -> float:

        normalized = asset.upper()
        totals = balance.get("total", {})
        aliases = {
            normalized,
            f"X{normalized}",
            f"Z{normalized}",
        }

        for key, value in totals.items():
            if str(key).upper() in aliases:
                return float(value or 0)

        return 0.0


APP_STATE = WebCommandCenter()


class RogueCircuitRequestHandler(BaseHTTPRequestHandler):

    server_version = "CircuitAlpha/1.0"

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

        if not self._authorized():
            self._send_json(
                {"error": "Unauthorized."},
                HTTPStatus.UNAUTHORIZED,
            )
            return

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
            elif parsed.path == "/api/schedule/daily-paper":
                data = APP_STATE.apply_daily_schedule(payload)
            elif parsed.path == "/api/credentials/kraken":
                data = APP_STATE.store_credentials(payload)
            elif parsed.path == "/api/kraken/check":
                data = APP_STATE.check_kraken_connection()
            elif parsed.path == "/api/kraken/use-target":
                data = APP_STATE.use_target_symbol()
            elif parsed.path == "/api/markets/scan":
                data = APP_STATE.scan_market_opportunities(payload)
            elif parsed.path == "/api/trading/run-once":
                data = APP_STATE.run_one_cycle_response()
            elif parsed.path == "/api/trading/mode":
                data = APP_STATE.set_execution_mode(payload)
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

    def _authorized(self):

        token = self.headers.get("X-Rogue-Token")
        auth_header = self.headers.get("Authorization", "")

        if not token and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()

        return APP_STATE.auth.verify(token)

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
    print(f"Circuit Alpha browser app: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
