import time

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
from risk.position_manager import PositionManager
from risk.position_size import PositionSizer
from risk.risk_manager import RiskManager


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
        self.decisions: dict[str, StrategyDecision] = {}
        self.cycles = 0

    def run_forever(self):

        self.console.print(
            "[bold yellow]PAPER[/bold yellow]"
            if PAPER_TRADING
            else "[bold red]LIVE[/bold red]"
        )

        while True:
            self.run_once()
            time.sleep(LIVE_LOOP_SECONDS)

    def run_once(self):

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

            self._execute_signal(symbol, signal)

        self.cycles += 1

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

        return decision

    def _execute_signal(self, symbol: str, signal):

        if (
            signal.action == HOLD
            or signal.confidence < MIN_SIGNAL_CONFIDENCE
        ):
            return

        if signal.action == BUY:
            self._buy(symbol, signal)
            return

        if signal.action == SELL:
            self._sell(symbol, signal)

    def _buy(self, symbol: str, signal):

        if not self.risk.can_open_trade():
            self.console.print(
                f"{symbol} buy skipped by risk controls"
            )
            return

        quantity = self.sizer.calculate_quantity(
            self.portfolio.cash,
            signal.price,
        )
        quantity = min(
            quantity,
            MAX_ORDER_NOTIONAL / signal.price,
        )

        if PAPER_TRADING:
            self.positions.open_position(signal, quantity)
            self.console.print(
                f"{symbol} paper buy quantity={quantity:.8f}"
            )
            return

        self._place_live_order(symbol, "buy", quantity)
        self.positions.open_position(signal, quantity)

    def _sell(self, symbol: str, signal):

        if not self.portfolio.has_open_position():
            return

        quantity = self.portfolio.open_trades[0].quantity

        if PAPER_TRADING:
            self.positions.close_position(signal)
            self.console.print(
                f"{symbol} paper sell quantity={quantity:.8f}"
            )
            return

        self._place_live_order(symbol, "sell", quantity)
        self.positions.close_position(signal)

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
