from accounting.ledger import InvestmentLedger
from analytics.chart_data import ChartDataBuilder


def test_chart_data_builder_returns_equity_drawdown_and_pnl(tmp_path):
    ledger = InvestmentLedger(tmp_path / "ledger.sqlite3")
    builder = ChartDataBuilder()

    ledger.add_deposit(1_000)
    ledger.record_snapshot(
        total_value=1_000,
        cash_value=1_000,
        positions_value=0,
        source="test",
    )
    ledger.record_snapshot(
        total_value=900,
        cash_value=900,
        positions_value=0,
        source="test",
    )
    ledger.record_snapshot(
        total_value=1_100,
        cash_value=1_100,
        positions_value=0,
        source="test",
    )

    data = builder.build(ledger)

    assert [point["value"] for point in data["equity_curve"]] == [
        1_000,
        900,
        1_100,
    ]
    assert data["drawdown"][1]["drawdown"] == 0.1
    assert data["daily_pnl"][1]["pnl"] == -100
    assert data["net_growth"] == 100
