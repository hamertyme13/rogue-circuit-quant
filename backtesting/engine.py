from backtesting.execution import ExecutionEngine


class BacktestEngine:

    def __init__(
        self,
        strategy,
        portfolio,
    ):

        self.strategy = strategy

        self.execution = ExecutionEngine(
            portfolio,
        )

    def run(self, df):

        for i in range(50, len(df)):

            current = df.iloc[: i + 1]

            signals = self.strategy.generate_signals(
                current
            )

            for signal in signals:

                self.execution.execute(signal)

        return self.execution.portfolio