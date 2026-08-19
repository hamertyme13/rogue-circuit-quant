import hmac
import hashlib


class TokenAuth:

    def __init__(self, token: str = ""):

        self._token_digest = self._digest(token)
        self.required = bool(token)

    def verify(self, token: str | None) -> bool:

        if not self.required:
            return True

        if not token:
            return False

        return hmac.compare_digest(
            self._token_digest,
            self._digest(token),
        )

    def status(self):

        return {
            "required": self.required,
            "configured": self.required,
        }

    def _digest(self, token: str) -> str:

        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()
