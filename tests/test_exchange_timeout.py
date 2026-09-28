from exchange.client import KrakenClient


def test_kraken_client_sets_bounded_request_timeout(monkeypatch):
    options_seen = []
    monkeypatch.setattr(
        "exchange.client.ccxt.kraken",
        lambda options: options_seen.append(options) or object(),
    )

    KrakenClient()

    assert options_seen[0]["timeout"] == 8000
    assert options_seen[0]["maxRetriesOnFailure"] == 0
