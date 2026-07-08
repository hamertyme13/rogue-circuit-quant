import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
from rich.console import Console

from ai.strategy_analysis import StrategyAnalyst, StrategyDecision
from config import (
    ALLOW_LIVE_TRADING,
    LIVE_CANDLE_LIMIT,
    LIVE_LOOP_SECONDS,
    LIVE_SYMBOLS,
    LIVE_TIMEFRAME,
    MAX_ORDER_NOTIONAL,
    MIN_SIGNAL_CONFIDENCE,
    PAPER_TRADING,
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
    mode: str = "paper"


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

    def run_forever(self):

        self.console.print(
            "[bold yellow]PAPER[/bold yellow]"
            if PAPER_TRADING
            else "[bold red]LIVE[/bold red]"
        )

        while True:
            self.run_once()
            time.sleep(self.loop_seconds)

    def run_once(self) -> list[TradeCycleEvent]:

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

        for symbol in LIVE_SYMBOLS:
            df = self._fetch_market_frame(symbol)

            if self._should_reoptimize(symbol):
                self.decisions[symbol] = self._optimize(symbol, df)

            decision = self.decisions.get(symbol)

            if decision is None:
                continue

            strategy = decision.build_strategy()
            signal = strategy.generate_signals(df)[-1]

            self.console.print(
                f"{symbol} {signal.action} "
                f"confidence={signal.confidence:.2f} "
                f"price={signal.price:,.2f}"
            )

            events.append(
                self._execute_signal(symbol, signal)
            )

        self.cycles += 1

        return events

    @property
    def mode(self) -> str:

        return "paper" if PAPER_TRADING else "live"

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

        if not self.risk.can_open_trade():
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
                reason="Risk controls blocked the buy.",
                mode=self.mode,
            )

        quantity = self.sizer.calculate_quantity(
            self.portfolio.cash,
            signal.price,
        )
        quantity = min(
            quantity,
            self.max_order_notional / signal.price,
        )

        if PAPER_TRADING:
            self.positions.open_position(signal, quantity)
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
            )

        order = self._place_live_order(symbol, "buy", quantity)
        self.positions.open_position(signal, quantity)

        return TradeCycleEvent(
            symbol=symbol,
            action=signal.action,
            confidence=signal.confidence,
            price=signal.price,
            strategy=signal.strategy,
            executed=True,
            quantity=quantity,
            order_id=self._order_id(order),
            reason="Live buy submitted.",
            mode=self.mode,
        )

    def _sell(self, symbol: str, signal) -> TradeCycleEvent:

        if not self.portfolio.has_open_position():
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

        quantity = self.portfolio.open_trades[0].quantity

        if PAPER_TRADING:
            self.positions.close_position(signal)
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

        order = self._place_live_order(symbol, "sell", quantity)
        self.positions.close_position(signal)

        return TradeCycleEvent(
            symbol=symbol,
            action=signal.action,
            confidence=signal.confidence,
            price=signal.price,
            strategy=signal.strategy,
            executed=True,
            quantity=quantity,
            order_id=self._order_id(order),
            reason="Live sell submitted.",
            mode=self.mode,
        )

    def _place_live_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ):

        if not ALLOW_LIVE_TRADING:
            raise RuntimeError(
                "Live order blocked. Set ALLOW_LIVE_TRADING=True "
                "only after validating paper trading."
            )

        order = self.client.create_market_order(
            symbol,
            side,
            quantity,
        )

        self.console.print(order)

        return order

    def _order_id(self, order: dict[str, Any] | None) -> str:

        if not order:
            return ""

        return str(order.get("id") or order.get("clientOrderId") or "")

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
