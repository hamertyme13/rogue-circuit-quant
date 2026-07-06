from pathlib import Path

# --------------------------------------------------
# PROJECT
# --------------------------------------------------

PROJECT_NAME = "Rogue Circuit Quant"
VERSION = "0.1.0"

# --------------------------------------------------
# DATA
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
HISTORICAL_DIR = DATA_DIR / "historical"

# --------------------------------------------------
# KRAKEN
# --------------------------------------------------

SYMBOLS = [
    "BTC/USD",
    "ETH/USD",
    "SOL/USD",
    "XRP/USD",
    "ADA/USD",
]

TIMEFRAMES = [
    "5m",
    "15m",
    "1h",
    "4h",
    "1d",
]

CANDLE_LIMIT = 720