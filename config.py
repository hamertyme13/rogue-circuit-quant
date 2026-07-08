import os

# ==========================
# Trading Mode
# ==========================

PAPER_TRADING = True

KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "")

KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "")

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

# ==========================
# Automated Trading
# ==========================

LIVE_SYMBOLS = ["BTC/USD"]

LIVE_TIMEFRAME = "5m"

LIVE_CANDLE_LIMIT = 300

LIVE_LOOP_SECONDS = 60

REOPTIMIZE_EVERY_CYCLES = 12

# ==========================
# Strategy Optimization
# ==========================

FAST_EMAS = [10, 15, 20]

SLOW_EMAS = [30, 40, 50]

RSI_PERIODS = [10, 14]

BUY_RSI_LEVELS = [55, 60]

SELL_RSI_LEVELS = [40, 45]
