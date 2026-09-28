import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
from rich.console import Console

from ai.strategy_analysis import StrategyAnalyst, StrategyDecision
from config import (
    ALLOW_LIVE_TRADING,
    LIVE_CANDLE_LIMIT,
    MARKET_CYCLE_DEADLINE_SECONDS,
    LIVE_CASH_RESERVE_RATE,
    LIVE_LOOP_SECONDS,
    LIVE_SLIPPAGE_RATE,
    LIVE_SYMBOLS,
    LIVE_TAKER_FEE_RATE,
    LIVE_TIMEFRAME,
    MAX_ORDER_NOTIONAL,
    MAX_OPEN_POSITIONS,
    MAX_PORTFOLIO_EXPOSURE,
    MAX_ASSET_EXPOSURE,
    MIN_CASH_RESERVE,
    MIN_SIGNAL_CONFIDENCE,
    OPPORTUNITY_MIN_CONFIDENCE,
    OPPORTUNITY_MIN_NET_PROFIT,
    OPPORTUNITY_MIN_WIN_RATE,
    EXECUTION_MODE,
    REOPTIMIZE_EVERY_CYCLES,
    STARTING_BALANCE,
)
from exchange.client import KrakenClient
from models.constants import BUY, HOLD, SELL
from optimization.optimizer import StrategyOptimizer
from risk.portfolio import Portfolio
from risk.kill_switch import KillSwitch
from risk.position_manager import PositionManager
from risk.position_size import PositionSizer
from risk.risk_manager import RiskManager
from risk.allocation import PortfolioAllocator
from live.execution_safety import (
    EXECUTION_MODES,
    LIMITED_LIVE,
    PAPER,
    SHADOW,
    LiveExecutionSafety,
)


@dataclass
class TradeCycleEvent:

    symbol: str
    action: str
    confidence: float
    price: float
    strategy: str
    executed: bool
    quantity: float = 0.0
    reason: str = ""
    order_id: str = ""
    order_status: str = ""
    mode: str = "paper"
    opportunity: bool = False
    opportunity_reason: str = ""


@dataclass
class StrategyPerformanceSnapshot:

    symbol: str
    strategy: str
    score: float
    net_profit: float
    win_rate: float
    drawdown: float
    trades: int
    rationale: str


@dataclass(frozen=True)
class MarketOpportunity:
    rank: int
    symbol: str
    action: str
    confidence: float
    price: float
    strategy: str
    score: float
    net_profit: float
    win_rate: float
    drawdown: float
    trades: int
    reason: str = ""


class AutomatedKrakenTrader:

    def __init__(
        self,
        client: KrakenClient | None = None,
        console: Console | None = None,
    ):

        self.client = client or KrakenClient()
        self.console = console or Console()
        self.analyst = StrategyAnalyst()
        self.optimizer = StrategyOptimizer()
        self.portfolio = Portfolio(STARTING_BALANCE)
        self.risk = RiskManager(self.portfolio)
        self.allocator = PortfolioAllocator(
            max_open_positions=MAX_OPEN_POSITIONS,
            max_portfolio_exposure=MAX_PORTFOLIO_EXPOSURE,
            max_asset_exposure=MAX_ASSET_EXPOSURE,
            min_cash_reserve=MIN_CASH_RESERVE,
        )
        self.sizer = PositionSizer()
        self.positions = PositionManager(self.portfolio)
        self.kill_switch = KillSwitch()
        self.decisions: dict[str, StrategyDecision] = {}
        self.strategy_performance: dict[
            str,
            StrategyPerformanceSnapshot,
        ] = {}
        self.cycles = 0
        self.max_order_notional = MAX_ORDER_NOTIONAL
        self.min_signal_confidence = MIN_SIGNAL_CONFIDENCE
        self.loop_seconds = LIVE_LOOP_SECONDS
        self.symbols = list(LIVE_SYMBOLS)
        self.execution_mode = (
            EXECUTION_MODE if EXECUTION_MODE in EXECUTION_MODES else PAPER
        )
        self.execution_safety = LiveExecutionSafety(
            taker_fee_rate=LIVE_TAKER_FEE_RATE,
            slippage_rate=LIVE_SLIPPAGE_RATE,
            reserve_rate=LIVE_CASH_RESERVE_RATE,
        )
        self.last_order_previews = {}
        self.last_allocation_decisions = {}
        self.live_symbol_allowlist = set()
        self.stop_requested = lambda: False
        self.cycle_deadline_seconds = MARKET_CYCLE_DEADLINE_SECONDS
        self.last_cycle_note = ""
        self.last_scan_note = ""

    def run_forever(self):

        self.console.print(
            f"[bold yellow]{self.execution_mode.upper()}[/bold yellow]"
        )

        while True:
            self.run_once()
            time.sleep(self.loop_seconds)

    def run_once(self) -> list[TradeCycleEvent]:

        self.last_cycle_note = ""

        if self.kill_switch.active():
            return [
                TradeCycleEvent(
                    symbol="SYSTEM",
                    action=HOLD,
                    confidence=0.0,
                    price=0.0,
                    strategy="KillSwitch",
                    executed=False,
                    reason="Emergency stop is active.",
                    mode=self.mode,
                )
            ]

        events = []
        deadline = time.monotonic() + self.cycle_deadline_seconds

        for symbol in self.symbols:
            if self.stop_requested():
                self.last_cycle_note = "Cycle stopped before all markets were checked."
                break
            if time.monotonic() >= deadline:
                self.last_cycle_note = (
                    "Cycle time budget reached before all markets were checked."
                )
                break
            try:
                events.append(self._run_symbol(symbol))
            except Exception as exc:
                self.console.print(f"{symbol} cycle failed: {exc}")
                events.append(TradeCycleEvent(
                    symbol=symbol,
                    action=HOLD,
                    confidence=0.0,
                    price=0.0,
                    strategy="MarketError",
                    executed=False,
                    reason=f"Market cycle failed: {exc}",
                    mode=self.mode,
                ))

        self.cycles += 1

        return events

    def _run_symbol(self, symbol: str) -> TradeCycleEvent:

        df = self._fetch_market_frame(symbol)

        if self._should_reoptimize(symbol):
            self.decisions[symbol] = self._optimize(symbol, df)

        decision = self.decisions.get(symbol)

        if decision is None:
            raise RuntimeError("No strategy decision is available.")

        strategy = decision.build_strategy()
        signal = strategy.generate_signals(df)[-1]
        self.portfolio.update_market_price(symbol, signal.price)

        self.console.print(
            f"{symbol} {signal.action} "
            f"confidence={signal.confidence:.2f} "
            f"price={signal.price:,.2f}"
        )

        return self._execute_signal(symbol, signal)

    def scan_markets(self, symbols: list[str]) -> list[MarketOpportunity]:

        opportunities = []
        self.last_scan_note = ""
        deadline = time.monotonic() + self.cycle_deadline_seconds

        for symbol in symbols:
            if self.stop_requested():
                self.last_scan_note = "Market scan stopped before all markets were checked."
                break
            if time.monotonic() >= deadline:
                self.last_scan_note = (
                    "Market scan time budget reached before all markets were checked."
                )
                break
            try:
                df = self._fetch_market_frame(symbol)
                decision = self._optimize(symbol, df)
                signal = decision.build_strategy().generate_signals(df)[-1]
                performance = self.strategy_performance[symbol]
                score = self._market_score(performance, signal.confidence)
                opportunities.append(MarketOpportunity(
                    rank=0,
                    symbol=symbol,
                    action=signal.action,
                    confidence=float(signal.confidence),
                    price=float(signal.price),
                    strategy=signal.strategy,
                    score=score,
                    net_profit=performance.net_profit,
                    win_rate=performance.win_rate,
                    drawdown=performance.drawdown,
                    trades=performance.trades,
                    reason=performance.rationale,
                ))
            except Exception as exc:
                self.console.print(f"{symbol} scan failed: {exc}")

        ranked = sorted(
            opportunities,
            key=lambda item: (item.score, item.confidence),
            reverse=True,
        )
        return [
            MarketOpportunity(**{**item.__dict__, "rank": index})
            for index, item in enumerate(ranked, start=1)
        ]

    @staticmethod
    def _market_score(performance, confidence: float) -> float:

        return round(
            performance.score
            * max(0.0, float(confidence))
            * max(0.0, 1.0 - float(performance.drawdown)),
            4,
        )

    @property
    def mode(self) -> str:

        return self.execution_mode

    def set_execution_mode(self, mode: str):

        normalized = str(mode or "").lower()
        if normalized not in EXECUTION_MODES:
            raise ValueError(f"Unsupported execution mode: {mode}")
        self.execution_mode = normalized

    def emergency_stop(self):

        self.kill_switch.stop()

    def resume_trading(self):

        self.kill_switch.resume()

    def _should_reoptimize(self, symbol: str) -> bool:

        return (
            symbol not in self.decisions
            or self.cycles % REOPTIMIZE_EVERY_CYCLES == 0
        )

    def _optimize(
        self,
        symbol: str,
        df: pd.DataFrame,
    ) -> StrategyDecision:

        results = self.optimizer.optimize(df)
        decision = self.analyst.choose_best(results)

        best = decision.result

        self.console.print(
            f"{symbol} strategy score={decision.score:.2f} "
            f"profit={best.net_profit:,.2f} "
            f"win_rate={best.win_rate:.2%} "
            f"drawdown={best.drawdown:.2%}"
        )

        self.strategy_performance[symbol] = (
            StrategyPerformanceSnapshot(
                symbol=symbol,
                strategy="Momentum",
                score=decision.score,
                net_profit=best.net_profit,
                win_rate=best.win_rate,
                drawdown=best.drawdown,
                trades=best.trades,
                rationale=decision.rationale,
            )
        )

        return decision

    def _execute_signal(self, symbol: str, signal) -> TradeCycleEvent:

        if (
            signal.action == HOLD
            or signal.confidence < self.min_signal_confidence
        ):
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                reason="Signal held or confidence was below threshold.",
                mode=self.mode,
                opportunity=self._is_opportunity(symbol, signal),
                opportunity_reason=self._opportunity_reason(symbol),
            )

        if signal.action == BUY:
            return self._buy(symbol, signal)

        if signal.action == SELL:
            return self._sell(symbol, signal)

        return TradeCycleEvent(
            symbol=symbol,
            action=signal.action,
            confidence=signal.confidence,
            price=signal.price,
            strategy=signal.strategy,
            executed=False,
            reason="Unsupported signal action.",
            mode=self.mode,
        )

    def _buy(self, symbol: str, signal) -> TradeCycleEvent:

        if self.mode == LIMITED_LIVE and symbol not in self.live_symbol_allowlist:
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                reason="Live buy blocked: market has not passed promotion gates.",
                mode=self.mode,
                opportunity=self._is_opportunity(symbol, signal),
                opportunity_reason=self._opportunity_reason(symbol),
            )

        if self.mode == SHADOW:
            return self._shadow_buy(symbol, signal)

        if not self.risk.can_open_trade(
            symbol,
            enforce_position_limit=False,
        ):
            self.console.print(
                f"{symbol} buy skipped by risk controls"
            )
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                reason="Risk controls blocked the buy: market already open, "
                "position limit reached, or loss guard active.",
                mode=self.mode,
                opportunity=self._is_opportunity(symbol, signal),
                opportunity_reason=self._opportunity_reason(symbol),
            )

        quantity = self.sizer.calculate_quantity(
            self.portfolio.cash,
            signal.price,
        )
        quantity = min(
            quantity,
            self.max_order_notional / signal.price,
        )
        allocation = self.allocator.allocate(
            self.portfolio,
            symbol,
            quantity * signal.price,
            self.max_order_notional,
        )
        self.last_allocation_decisions[symbol] = allocation.as_dict()
        if not allocation.allowed:
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                reason=f"Allocation blocked: {allocation.reason}",
                mode=self.mode,
                opportunity=self._is_opportunity(symbol, signal),
                opportunity_reason=self._opportunity_reason(symbol),
            )
        quantity = allocation.approved_notional / signal.price

        if self.mode == PAPER:
            self.positions.open_position(
                symbol,
                signal,
                quantity,
            )
            self.console.print(
                f"{symbol} paper buy quantity={quantity:.8f}"
            )
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=True,
                quantity=quantity,
                reason="Paper buy opened.",
                mode=self.mode,
                opportunity=self._is_opportunity(symbol, signal),
                opportunity_reason=self._opportunity_reason(symbol),
            )

        preview = self.execution_safety.preview(
            self.client,
            symbol,
            "buy",
            quantity,
            signal.price,
        )
        self.last_order_previews[symbol] = preview.as_dict()

        if not preview.valid:
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                quantity=preview.quantity,
                order_id=preview.client_order_id,
                reason="Order preview blocked: " + " ".join(preview.reasons),
                mode=self.mode,
                opportunity=self._is_opportunity(symbol, signal),
                opportunity_reason=self._opportunity_reason(symbol),
            )

        order = self._place_live_order(
            symbol,
            "buy",
            preview.quantity,
            preview.client_order_id,
        )
        order_id = self._order_id(order)
        order_status = self._order_status(order)
        filled_quantity = self._filled_quantity(order)
        fill_price = self._fill_price(order, signal.price)

        if filled_quantity <= 0:
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                quantity=0.0,
                order_id=order_id,
                order_status=order_status,
                reason="Live buy submitted; fill was not confirmed.",
                mode=self.mode,
                opportunity=self._is_opportunity(symbol, signal),
                opportunity_reason=self._opportunity_reason(symbol),
            )

        self.positions.open_position(
            symbol,
            signal,
            filled_quantity,
            order_id=order_id,
            order_status=order_status,
            fill_price=fill_price,
        )

        return TradeCycleEvent(
            symbol=symbol,
            action=signal.action,
            confidence=signal.confidence,
            price=signal.price,
            strategy=signal.strategy,
            executed=True,
            quantity=filled_quantity,
            order_id=order_id,
            order_status=order_status,
            reason="Live buy filled and tracked.",
            mode=self.mode,
            opportunity=self._is_opportunity(symbol, signal),
            opportunity_reason=self._opportunity_reason(symbol),
        )

    def _shadow_buy(self, symbol: str, signal) -> TradeCycleEvent:
        quantity = self.max_order_notional / signal.price
        preview = self.execution_safety.preview(
            self.client,
            symbol,
            "buy",
            quantity,
            signal.price,
            fit_to_available=True,
        )
        self.last_order_previews[symbol] = preview.as_dict()

        if not preview.valid:
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                quantity=preview.quantity,
                order_id=preview.client_order_id,
                reason="Shadow preview blocked: " + " ".join(preview.reasons),
                mode=self.mode,
                opportunity=self._is_opportunity(symbol, signal),
                opportunity_reason=self._opportunity_reason(symbol),
            )

        return TradeCycleEvent(
            symbol=symbol,
            action=signal.action,
            confidence=signal.confidence,
            price=signal.price,
            strategy=signal.strategy,
            executed=False,
            quantity=preview.quantity,
            order_id=preview.client_order_id,
            order_status="validated",
            reason=(
                "Shadow BUY validated against Kraken balance and rules; "
                "no Kraken order sent. "
                f"Estimated fee={preview.estimated_fee:.8f} "
                f"{preview.balance_asset}, slippage="
                f"{preview.estimated_slippage:.8f}."
            ),
            mode=self.mode,
            opportunity=self._is_opportunity(symbol, signal),
            opportunity_reason=self._opportunity_reason(symbol),
        )

    def _sell(self, symbol: str, signal) -> TradeCycleEvent:

        if not self.portfolio.has_open_position_for(symbol):
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                reason="No open position to sell.",
                mode=self.mode,
            )

        open_trade = self.portfolio.open_position_for(symbol)
        quantity = open_trade.quantity

        if self.mode == PAPER:
            self.positions.close_position(
                symbol,
                signal,
            )
            self.console.print(
                f"{symbol} paper sell quantity={quantity:.8f}"
            )
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=True,
                quantity=quantity,
                reason="Paper sell closed.",
                mode=self.mode,
            )

        preview = self.execution_safety.preview(
            self.client,
            symbol,
            "sell",
            quantity,
            signal.price,
        )
        self.last_order_previews[symbol] = preview.as_dict()

        if not preview.valid:
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                quantity=preview.quantity,
                order_id=preview.client_order_id,
                reason="Order preview blocked: " + " ".join(preview.reasons),
                mode=self.mode,
            )

        if self.mode == SHADOW:
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                quantity=preview.quantity,
                order_id=preview.client_order_id,
                order_status="validated",
                reason="Shadow SELL validated; no Kraken order sent.",
                mode=self.mode,
            )

        order = self._place_live_order(
            symbol,
            "sell",
            preview.quantity,
            preview.client_order_id,
        )
        order_id = self._order_id(order)
        order_status = self._order_status(order)
        filled_quantity = self._filled_quantity(order)

        if filled_quantity <= 0:
            return TradeCycleEvent(
                symbol=symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price,
                strategy=signal.strategy,
                executed=False,
                quantity=0.0,
                order_id=order_id,
                order_status=order_status,
                reason="Live sell submitted; fill was not confirmed.",
                mode=self.mode,
            )

        self.positions.close_position(
            symbol,
            signal,
        )

        return TradeCycleEvent(
            symbol=symbol,
            action=signal.action,
            confidence=signal.confidence,
            price=signal.price,
            strategy=signal.strategy,
            executed=True,
            quantity=min(filled_quantity, quantity),
            order_id=order_id,
            order_status=order_status,
            reason="Live sell filled and tracked.",
            mode=self.mode,
        )

    def _place_live_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        client_order_id: str,
    ):

        if self.mode != LIMITED_LIVE or not ALLOW_LIVE_TRADING:
            raise RuntimeError(
                "Live order blocked. Set ALLOW_LIVE_TRADING=True "
                "only after validating paper trading."
            )

        order = self.client.create_market_order(
            symbol,
            side,
            quantity,
            client_order_id=client_order_id,
        )

        order_id = self._order_id(order)
        status = self._order_status(order)
        if order_id and status not in {"closed", "filled"}:
            order = self.client.fetch_order(order_id, symbol)

        self.console.print(order)

        return order

    def _order_id(self, order: dict[str, Any] | None) -> str:

        if not order:
            return ""

        return str(order.get("id") or order.get("clientOrderId") or "")

    def _order_status(self, order: dict[str, Any] | None) -> str:

        if not order:
            return ""

        return str(order.get("status") or "")

    def _filled_quantity(self, order: dict[str, Any] | None) -> float:

        if not order:
            return 0.0

        try:
            return float(order.get("filled") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _fill_price(
        self,
        order: dict[str, Any] | None,
        fallback_price: float,
    ) -> float:

        if not order:
            return fallback_price

        for key in ("average", "price"):
            try:
                value = float(order.get(key) or 0.0)
            except (TypeError, ValueError):
                value = 0.0

            if value > 0:
                return value

        cost = order.get("cost")
        filled = self._filled_quantity(order)

        try:
            cost_value = float(cost or 0.0)
        except (TypeError, ValueError):
            cost_value = 0.0

        if cost_value > 0 and filled > 0:
            return cost_value / filled

        return fallback_price

    def _is_opportunity(self, symbol: str, signal) -> bool:

        performance = self.strategy_performance.get(symbol)

        return (
            signal.action == BUY
            and signal.confidence >= OPPORTUNITY_MIN_CONFIDENCE
            and performance is not None
            and performance.net_profit >= OPPORTUNITY_MIN_NET_PROFIT
            and performance.win_rate >= OPPORTUNITY_MIN_WIN_RATE
        )

    def _opportunity_reason(self, symbol: str) -> str:

        performance = self.strategy_performance.get(symbol)

        if performance is None:
            return ""

        return (
            f"{symbol} has a qualified BUY signal. "
            f"Backtest net profit={performance.net_profit:.2f}, "
            f"win rate={performance.win_rate:.2%}, "
            f"drawdown={performance.drawdown:.2%}. "
            "This is an opportunity alert, not a profit guarantee."
        )

    def _fetch_market_frame(self, symbol: str) -> pd.DataFrame:

        candles = self.client.fetch_ohlcv(
            symbol,
            LIVE_TIMEFRAME,
            limit=LIVE_CANDLE_LIMIT,
        )

        df = pd.DataFrame(
            candles,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            unit="ms",
        )

        return df
