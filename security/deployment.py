from dataclasses import dataclass


MODES = {
    "local": {
        "live_trading_allowed": False,
        "external_access": False,
        "description": "Local command center mode.",
    },
    "paper": {
        "live_trading_allowed": False,
        "external_access": True,
        "description": "Paper-trading web mode.",
    },
    "live_locked": {
        "live_trading_allowed": False,
        "external_access": True,
        "description": "Production-like mode with live trading locked.",
    },
    "live_enabled": {
        "live_trading_allowed": True,
        "external_access": True,
        "description": "Live trading enabled mode.",
    },
    "maintenance": {
        "live_trading_allowed": False,
        "external_access": False,
        "description": "Read-only maintenance mode.",
    },
}


@dataclass
class DeploymentMode:

    name: str
    live_trading_allowed: bool
    external_access: bool
    description: str


def resolve_mode(name: str) -> DeploymentMode:

    normalized = (name or "local").lower()
    config = MODES.get(normalized, MODES["local"])

    return DeploymentMode(
        name=normalized if normalized in MODES else "local",
        live_trading_allowed=config["live_trading_allowed"],
        external_access=config["external_access"],
        description=config["description"],
    )
