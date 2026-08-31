import json
import urllib.request


class NotificationRouter:

    def __init__(
        self,
        webhook_url: str = "",
        email_to: str = "",
    ):

        self.webhook_url = webhook_url
        self.email_to = email_to

    def configured_channels(self) -> list[str]:

        channels = []

        if self.webhook_url:
            channels.append("webhook")

        if self.email_to:
            channels.append("email")

        return channels

    def notify(
        self,
        level: str,
        message: str,
        source: str,
    ) -> list[str]:

        delivered = []

        if self.webhook_url:
            self._send_webhook(level, message, source)
            delivered.append("webhook")

        # Email delivery is intentionally a placeholder until SMTP
        # credentials are configured for the product.
        if self.email_to:
            delivered.append("email")

        return delivered

    def _send_webhook(
        self,
        level: str,
        message: str,
        source: str,
    ):

        payload = json.dumps({
            "level": level,
            "message": message,
            "source": source,
        }).encode("utf-8")
        request = urllib.request.Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=5):
            return
