from datetime import datetime, timezone

from live.trader import MarketOpportunity
from models.signal import Signal
from web_app import WebCommandCenter


class FakeKrakenClient:

    has_credentials = True

    def __init__(
        self,
        market_available=True,
        balance=100.0,
        price=0.045,
    ):
        self.market_available = market_available
        self.balance = balance
        self.price = price

    def has_market(self, symbol):
        return self.market_available

    def fetch_balance(self):
        return {
            "total": {
                "QUID": self.balance,
            }
        }

    def fetch_ticker(self, symbol):
        return {
            "last": self.price,
        }

    def load_markets(self):
        return {
            symbol: {
                "quote": "USD",
                "spot": True,
                "active": True,
            }
            for symbol in ("BTC/USD", "ETH/USD", "SOL/USD", "QUID/USD")
        }

    def fetch_tickers(self, symbols=None):
        volumes = {
            "BTC/USD": 1000,
            "ETH/USD": 900,
            "SOL/USD": 800,
            "QUID/USD": 20,
        }
        return {
            symbol: {"quoteVolume": volumes[symbol]}
            for symbol in symbols
        }


def center(tmp_path):
    command_center = WebCommandCenter(
        tmp_path / "ledger.sqlite3",
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )
    command_center.credential_vault.store_kraken_credentials(
        "key",
        "secret",
    )
    return command_center


def test_kraken_target_asset_status_detects_ready_paper_mode(tmp_path):
    command_center = center(tmp_path)
    command_center.client = FakeKrakenClient(
        market_available=True,
        balance=200,
        price=0.05,
    )
    command_center.trader.symbols = ["QUID/USD"]

    status = command_center.target_asset_status(refresh=True)

    assert status["asset"] == "QUID"
    assert status["symbol"] == "QUID/USD"
    assert status["market_available"] is True
    assert status["balance"] == 200
    assert status["estimated_usd"] == 10
    assert status["ready_for_paper"] is True
    assert status["ready_for_live"] is False


def test_kraken_target_asset_status_requires_bot_symbol(tmp_path):
    command_center = center(tmp_path)
    command_center.client = FakeKrakenClient(
        market_available=True,
        balance=200,
        price=0.05,
    )

    status = command_center.target_asset_status(refresh=True)

    assert status["configured_for_bot"] is False
    assert status["ready_for_paper"] is False
    assert "Set the bot symbol" in status["message"]


def test_kraken_target_asset_status_locks_missing_market(tmp_path):
    command_center = center(tmp_path)
    command_center.client = FakeKrakenClient(
        market_available=False,
        balance=200,
    )

    status = command_center.target_asset_status(refresh=True)

    assert status["market_available"] is False
    assert status["ready_for_paper"] is False
    assert "not currently available" in status["message"]


def test_kraken_check_caches_status_in_state(tmp_path):
    command_center = center(tmp_path)
    command_center.client = FakeKrakenClient(
        market_available=True,
        balance=50,
        price=0.05,
    )
    command_center.trader.symbols = ["QUID/USD"]

    state = command_center.check_kraken_connection()

    assert state["target_asset"]["balance"] == 50
    assert state["target_asset"]["ready_for_paper"] is True
    assert "QUID balance found" in state["message"]


def test_use_target_symbol_configures_bot_for_quid(tmp_path):
    command_center = center(tmp_path)
    command_center.client = FakeKrakenClient(
        market_available=True,
        balance=50,
        price=0.05,
    )

    state = command_center.use_target_symbol()

    assert state["service"]["symbols"] == ["QUID/USD"]
    assert state["target_asset"]["configured_for_bot"] is True
    assert state["target_asset"]["ready_for_paper"] is True


def test_market_scan_selects_multiple_ranked_paper_symbols(tmp_path):
    command_center = center(tmp_path)
    command_center.client = FakeKrakenClient()
    command_center.trader.client = command_center.client

    def scan_markets(symbols):
        return [
            MarketOpportunity(
                rank=index,
                symbol=symbol,
                action="BUY",
                confidence=0.8,
                price=10.0,
                strategy="Momentum",
                score=100 - index,
                net_profit=25.0,
                win_rate=0.6,
                drawdown=0.04,
                trades=10,
            )
            for index, symbol in enumerate(symbols, start=1)
        ]

    command_center.trader.scan_markets = scan_markets
    state = command_center.scan_market_opportunities({
        "scan_limit": 4,
        "active_limit": 3,
    })

    assert len(state["market_opportunities"]) == 4
    assert len(state["service"]["symbols"]) == 3
    assert command_center.ledger.get_setting("live_symbols", "")


def test_market_scan_retains_open_paper_symbol(tmp_path):
    command_center = center(tmp_path)
    command_center.client = FakeKrakenClient()
    command_center.trader.client = command_center.client
    command_center.trader.positions.open_position(
        "QUID/USD",
        Signal(
            timestamp=datetime.now(timezone.utc),
            action="BUY",
            price=0.05,
            confidence=0.9,
            strategy="Momentum",
        ),
        10,
    )
    command_center.trader.scan_markets = lambda symbols: [
        MarketOpportunity(
            rank=index,
            symbol=symbol,
            action="BUY",
            confidence=0.8,
            price=10.0,
            strategy="Momentum",
            score=100 - index,
            net_profit=25.0,
            win_rate=0.6,
            drawdown=0.04,
            trades=10,
        )
        for index, symbol in enumerate(symbols, start=1)
    ]

    state = command_center.scan_market_opportunities({
        "scan_limit": 4,
        "active_limit": 3,
    })

    assert "QUID/USD" in state["service"]["symbols"]
    assert len(state["service"]["symbols"]) == 3
