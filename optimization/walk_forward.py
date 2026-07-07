from optimization.data_split import DataSplitter
from optimization.optimizer import StrategyOptimizer

from strategies.momentum import MomentumStrategy
from risk.portfolio import Portfolio
from backtesting.engine import BacktestEngine
from backtesting.metrics import PerformanceMetrics


class WalkForwardTest:

    def run(self, df):

        splitter = DataSplitter()

        train, test = splitter.split(df)

        optimizer = StrategyOptimizer()

        train_results = optimizer.optimize(train)

        train_results.sort(
            key=lambda x: x.net_profit,
            reverse=True,
        )

        best = train_results[0]
    
        best_strategy = MomentumStrategy(
            fast_ema=best.fast_ema,
            slow_ema=best.slow_ema,
            rsi_period=best.rsi_period,
            buy_rsi=best.buy_rsi,
            sell_rsi=best.sell_rsi,
        )

        portfolio = Portfolio()

        engine = BacktestEngine(
            best_strategy,
            portfolio,
        )

        portfolio = engine.run(test)

        metrics = PerformanceMetrics(portfolio)

        return best, metrics