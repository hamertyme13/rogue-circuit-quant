class FeeModel:

    def __init__(
        self,
        maker_fee=0.0016,
        taker_fee=0.0026,
    ):

        self.maker_fee = maker_fee

        self.taker_fee = taker_fee

    def calculate(
        self,
        trade_value,
        taker=True,
    ):

        fee = (
            self.taker_fee
            if taker
            else self.maker_fee
        )

        return trade_value * fee