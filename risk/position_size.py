class PositionSizer:

    def __init__(self, risk_percent=0.02):
        self.risk_percent = risk_percent

    def calculate_quantity(
        self,
        cash: float,
        price: float,
    ) -> float:

        dollars = cash * self.risk_percent

        return dollars / price