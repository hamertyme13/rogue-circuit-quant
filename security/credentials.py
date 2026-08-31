import json
from pathlib import Path

from cryptography.fernet import Fernet


class CredentialVault:

    def __init__(
        self,
        vault_path: str | Path,
        key_path: str | Path,
    ):

        self.vault_path = Path(vault_path)
        self.key_path = Path(key_path)
        self.vault_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.key_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def store_kraken_credentials(
        self,
        api_key: str,
        api_secret: str,
    ):

        if not api_key or not api_secret:
            raise ValueError(
                "Kraken API key and secret are required."
            )

        fernet = self._fernet()
        payload = {
            "kraken": {
                "api_key": fernet.encrypt(
                    api_key.encode("utf-8")
                ).decode("utf-8"),
                "api_secret": fernet.encrypt(
                    api_secret.encode("utf-8")
                ).decode("utf-8"),
            }
        }

        self.vault_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def load_kraken_credentials(self) -> dict[str, str] | None:

        if not self.vault_path.exists():
            return None

        payload = json.loads(
            self.vault_path.read_text(encoding="utf-8")
        )
        encrypted = payload.get("kraken")

        if not encrypted:
            return None

        fernet = self._fernet()

        return {
            "api_key": fernet.decrypt(
                encrypted["api_key"].encode("utf-8")
            ).decode("utf-8"),
            "api_secret": fernet.decrypt(
                encrypted["api_secret"].encode("utf-8")
            ).decode("utf-8"),
        }

    def status(self) -> dict[str, bool]:

        return {
            "vault_exists": self.vault_path.exists(),
            "key_exists": self.key_path.exists(),
            "kraken_configured": (
                self.load_kraken_credentials() is not None
                if self.vault_path.exists()
                else False
            ),
        }

    def _fernet(self) -> Fernet:

        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
            self.key_path.chmod(0o600)

        return Fernet(self.key_path.read_bytes())
