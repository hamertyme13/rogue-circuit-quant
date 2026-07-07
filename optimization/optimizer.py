from backtesting.engine import BacktestEngine
from backtesting.metrics import PerformanceMetrics
from optimization.result import OptimizationResult
from risk.portfolio import Portfolio
from strategies.momentum import MomentumStrategy
from config import (
    FAST_EMAS,
    SLOW_EMAS,
    RSI_PERIODS,
    BUY_RSI_LEVELS,
    SELL_RSI_LEVELS,
)


class StrategyOptimizer:

    def optimize(self, df):

        results = []

        for fast in FAST_EMAS:

            for slow in SLOW_EMAS:

                if fast >= slow:
                    continue

                for rsi in RSI_PERIODS:

                    for buy_rsi in BUY_RSI_LEVELS:

                        for sell_rsi in SELL_RSI_LEVELS:

                            strategy = MomentumStrategy(
                                fast_ema=fast,
                                slow_ema=slow,
                                rsi_period=rsi,
                                buy_rsi=buy_rsi,
                                sell_rsi=sell_rsi
                            )

                    portfolio = Portfolio()

                    engine = BacktestEngine(
                        strategy,
                        portfolio,
                    )

                    portfolio = engine.run(df)

                    metrics = PerformanceMetrics(
                        portfolio
                    )

                    results.append(
                        OptimizationResult(
                            fast_ema=fast,
                            slow_ema=slow,
                            rsi_period=rsi,
                            buy_rsi=buy_rsi,
                            sell_rsi=sell_rsi,
                            trades=portfolio.total_trades(),
                            win_rate=metrics.win_rate(),
                            net_profit=metrics.total_profit(),
                            drawdown=metrics.max_drawdown(),
                        )
                    )

        return results