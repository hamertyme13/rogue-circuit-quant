import os
from pathlib import Path

# ==========================
# Trading Mode
# ==========================

PAPER_TRADING = True

KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "")

KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "")

APP_AUTH_TOKEN = os.getenv("ROGUE_QUANT_AUTH_TOKEN", "")

APP_DEPLOYMENT_MODE = os.getenv(
    "ROGUE_QUANT_MODE",
    "local",
)

CREDENTIAL_VAULT_PATH = Path("data/credential_vault.json")

CREDENTIAL_VAULT_KEY_PATH = Path("data/credential_vault.key")

NOTIFICATION_WEBHOOK_URL = os.getenv(
    "ROGUE_QUANT_WEBHOOK_URL",
    "",
)

NOTIFICATION_EMAIL_TO = os.getenv(
    "ROGUE_QUANT_EMAIL_TO",
    "",
)

# ==========================
# Risk Controls
# ==========================

STARTING_BALANCE = 10_000

MAX_OPEN_POSITIONS = 1

MAX_POSITION_RISK = 0.02      # 2%

MAX_DAILY_LOSS = 0.03         # 3%

MAX_DRAWDOWN = 0.10           # 10%

ALLOW_SHORTS = False

ALLOW_LIVE_TRADING = False

MAX_ORDER_NOTIONAL = 250

MIN_SIGNAL_CONFIDENCE = 0.70

PAPER_VALIDATION_MIN_CYCLES = int(
    os.getenv("ROGUE_QUANT_PAPER_VALIDATION_MIN_CYCLES", "100")
)

PAPER_VALIDATION_MIN_CLOSED_TRADES = int(
    os.getenv("ROGUE_QUANT_PAPER_VALIDATION_MIN_CLOSED_TRADES", "10")
)

PAPER_VALIDATION_MAX_DRAWDOWN = float(
    os.getenv("ROGUE_QUANT_PAPER_VALIDATION_MAX_DRAWDOWN", str(MAX_DRAWDOWN))
)

PAPER_VALIDATION_MIN_GROWTH = float(
    os.getenv("ROGUE_QUANT_PAPER_VALIDATION_MIN_GROWTH", "0")
)

PAPER_VALIDATION_MIN_OPPORTUNITY_RATE = float(
    os.getenv("ROGUE_QUANT_PAPER_VALIDATION_MIN_OPPORTUNITY_RATE", "0.05")
)

OPPORTUNITY_MIN_CONFIDENCE = float(
    os.getenv(
        "ROGUE_QUANT_OPPORTUNITY_MIN_CONFIDENCE",
        str(MIN_SIGNAL_CONFIDENCE),
    )
)

OPPORTUNITY_MIN_WIN_RATE = float(
    os.getenv("ROGUE_QUANT_OPPORTUNITY_MIN_WIN_RATE", "0.55")
)

OPPORTUNITY_MIN_NET_PROFIT = float(
    os.getenv("ROGUE_QUANT_OPPORTUNITY_MIN_NET_PROFIT", "0")
)

# ==========================
# Automated Trading
# ==========================

LIVE_SYMBOLS = [
    symbol.strip()
    for symbol in os.getenv(
        "ROGUE_QUANT_LIVE_SYMBOLS",
        "BTC/USD",
    ).split(",")
    if symbol.strip()
]

TARGET_ASSET = os.getenv("ROGUE_QUANT_TARGET_ASSET", "QUID")

TARGET_SYMBOL = os.getenv(
    "ROGUE_QUANT_TARGET_SYMBOL",
    f"{TARGET_ASSET}/USD",
)

LIVE_TIMEFRAME = "5m"

LIVE_CANDLE_LIMIT = 300

LIVE_LOOP_SECONDS = 60

REOPTIMIZE_EVERY_CYCLES = 12

# ==========================
# Desktop Dashboard
# ==========================

LEDGER_DB_PATH = Path("data/rogue_circuit_ledger.sqlite3")

PORTFOLIO_ALERT_PERCENT = 0.05

# ==========================
# Strategy Optimization
# ==========================

FAST_EMAS = [10, 15, 20]

SLOW_EMAS = [30, 40, 50]

RSI_PERIODS = [10, 14]

BUY_RSI_LEVELS = [55, 60]

SELL_RSI_LEVELS = [40, 45]
