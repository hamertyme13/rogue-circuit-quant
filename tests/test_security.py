from security.auth import TokenAuth
from security.credentials import CredentialVault
from security.deployment import resolve_mode


def test_token_auth_allows_local_mode_without_token():
    auth = TokenAuth("")

    assert auth.verify(None) is True
    assert auth.status()["required"] is False


def test_token_auth_requires_matching_token():
    auth = TokenAuth("secret-token")

    assert auth.verify("secret-token") is True
    assert auth.verify("wrong-token") is False
    assert auth.verify(None) is False


def test_credential_vault_encrypts_and_loads_kraken_credentials(tmp_path):
    vault = CredentialVault(
        tmp_path / "vault.json",
        tmp_path / "vault.key",
    )

    vault.store_kraken_credentials(
        "api-key",
        "api-secret",
    )

    raw = (tmp_path / "vault.json").read_text(encoding="utf-8")
    credentials = vault.load_kraken_credentials()

    assert "api-secret" not in raw
    assert credentials == {
        "api_key": "api-key",
        "api_secret": "api-secret",
    }
    assert vault.status()["kraken_configured"] is True


def test_deployment_modes_lock_live_trading_by_default():
    local = resolve_mode("local")
    live = resolve_mode("live_enabled")
    unknown = resolve_mode("missing")

    assert local.live_trading_allowed is False
    assert live.live_trading_allowed is True
    assert unknown.name == "local"
