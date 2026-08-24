from live.execution_safety import LiveExecutionSafety


class FakeClient:
    def __init__(self, permissions=None, usd=100, btc=0.01):
        self.permissions = permissions or []
        self.usd = usd
        self.btc = btc

    def fetch_api_key_info(self):
        return {"result": {"permissions": self.permissions}}

    def market(self, symbol):
        return {
            "base": "BTC",
            "quote": "USD",
            "limits": {"amount": {"min": 0.0001}},
        }

    def fetch_balance(self):
        return {"free": {"USD": self.usd, "BTC": self.btc}}

    def amount_to_precision(self, symbol, quantity):
        return f"{quantity:.4f}"


def test_permission_check_requires_trading_and_forbids_withdrawals():
    safety = LiveExecutionSafety()
    required = [
        "query-funds",
        "query-open-trades",
        "query-closed-trades",
        "modify-trades",
        "close-trades",
    ]

    safe = safety.inspect_permissions(FakeClient(required))
    unsafe = safety.inspect_permissions(
        FakeClient(required + ["withdraw-funds"])
    )

    assert safe.safe_for_live is True
    assert unsafe.safe_for_live is False
    assert unsafe.forbidden == ("withdraw-funds",)


def test_order_preview_checks_minimum_fees_slippage_and_balance():
    safety = LiveExecutionSafety(
        taker_fee_rate=0.008,
        slippage_rate=0.002,
        reserve_rate=0.05,
    )

    valid = safety.preview(
        FakeClient(usd=100),
        "BTC/USD",
        "buy",
        0.001,
        50_000,
    )
    too_small = safety.preview(
        FakeClient(usd=100),
        "BTC/USD",
        "buy",
        0.00001,
        50_000,
    )
    insufficient = safety.preview(
        FakeClient(usd=10),
        "BTC/USD",
        "buy",
        0.001,
        50_000,
    )

    assert valid.valid is True
    assert valid.estimated_fee == 0.4
    assert valid.estimated_slippage == 0.1
    assert valid.client_order_id.startswith("ca-")
    assert too_small.valid is False
    assert any("minimum" in reason for reason in too_small.reasons)
    assert insufficient.valid is False
    assert "only" in insufficient.reasons[0]
