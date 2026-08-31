from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import uuid4


PAPER = "paper"
SHADOW = "shadow"
LIMITED_LIVE = "limited_live"
EXECUTION_MODES = {PAPER, SHADOW, LIMITED_LIVE}

REQUIRED_LIVE_PERMISSIONS = {
    "query-funds",
    "query-open-trades",
    "query-closed-trades",
    "modify-trades",
    "close-trades",
}
FORBIDDEN_LIVE_PERMISSIONS = {
    "withdraw-funds",
    "add-withdraw-address",
    "update-withdraw-address",
}


@dataclass(frozen=True)
class KrakenPermissionStatus:
    checked: bool
    safe_for_live: bool
    permissions: tuple[str, ...]
    missing: tuple[str, ...]
    forbidden: tuple[str, ...]
    message: str

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class OrderPreview:
    valid: bool
    symbol: str
    side: str
    quantity: float
    price: float
    notional: float
    estimated_fee: float
    estimated_slippage: float
    required_balance: float
    available_balance: float
    balance_asset: str
    minimum_quantity: float
    client_order_id: str
    reasons: tuple[str, ...]

    def as_dict(self):
        return asdict(self)


class LiveExecutionSafety:
    def __init__(
        self,
        taker_fee_rate: float = 0.008,
        slippage_rate: float = 0.002,
        reserve_rate: float = 0.05,
    ):
        self.taker_fee_rate = float(taker_fee_rate)
        self.slippage_rate = float(slippage_rate)
        self.reserve_rate = float(reserve_rate)

    def inspect_permissions(self, client) -> KrakenPermissionStatus:
        try:
            payload = client.fetch_api_key_info()
            result = payload.get("result", payload)
            permissions = set(result.get("permissions", []))
        except Exception as exc:
            return KrakenPermissionStatus(
                checked=False,
                safe_for_live=False,
                permissions=(),
                missing=tuple(sorted(REQUIRED_LIVE_PERMISSIONS)),
                forbidden=(),
                message=f"Could not inspect Kraken API permissions: {exc}",
            )

        missing = REQUIRED_LIVE_PERMISSIONS - permissions
        forbidden = FORBIDDEN_LIVE_PERMISSIONS & permissions
        safe = not missing and not forbidden

        if safe:
            message = "Kraken API permissions are suitable for limited live trading."
        elif forbidden:
            message = "Remove withdrawal permissions before live trading."
        else:
            message = "Kraken API key is missing required trading permissions."

        return KrakenPermissionStatus(
            checked=True,
            safe_for_live=safe,
            permissions=tuple(sorted(permissions)),
            missing=tuple(sorted(missing)),
            forbidden=tuple(sorted(forbidden)),
            message=message,
        )

    def preview(
        self,
        client,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> OrderPreview:
        market = client.market(symbol)
        balance = client.fetch_balance()
        base = str(market.get("base") or symbol.split("/")[0])
        quote = str(market.get("quote") or symbol.split("/")[1])
        minimum = float(
            ((market.get("limits") or {}).get("amount") or {}).get("min")
            or 0.0
        )
        precise_quantity = float(client.amount_to_precision(symbol, quantity))
        notional = precise_quantity * float(price)
        fee = notional * self.taker_fee_rate
        slippage = notional * self.slippage_rate
        free = balance.get("free", {})
        reasons = []

        if precise_quantity <= 0:
            reasons.append("Order quantity rounds to zero at Kraken precision.")
        if minimum > 0 and precise_quantity < minimum:
            reasons.append(
                f"Quantity is below Kraken minimum of {minimum:g} {base}."
            )

        if side.lower() == "buy":
            asset = quote
            available = self._balance_amount(free, quote)
            required = (notional + fee + slippage) * (1 + self.reserve_rate)
        else:
            asset = base
            available = self._balance_amount(free, base)
            required = precise_quantity

        if required > available:
            reasons.append(
                f"Needs {required:.8f} {asset}; only {available:.8f} is free."
            )

        return OrderPreview(
            valid=not reasons,
            symbol=symbol,
            side=side.lower(),
            quantity=precise_quantity,
            price=float(price),
            notional=notional,
            estimated_fee=fee,
            estimated_slippage=slippage,
            required_balance=required,
            available_balance=available,
            balance_asset=asset,
            minimum_quantity=minimum,
            client_order_id=self.client_order_id(),
            reasons=tuple(reasons),
        )

    @staticmethod
    def client_order_id() -> str:
        return f"ca-{uuid4().hex[:15]}"

    @staticmethod
    def _balance_amount(free: dict, asset: str) -> float:
        aliases = {asset.upper(), f"X{asset.upper()}", f"Z{asset.upper()}"}
        for key, value in free.items():
            if str(key).upper() in aliases:
                return float(value or 0.0)
        return 0.0
