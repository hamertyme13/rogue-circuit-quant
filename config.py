# ==========================
# Trading Mode
# ==========================

PAPER_TRADING = True

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

# ==========================
# Strategy Optimization
# ==========================

FAST_EMAS = [10, 15, 20]

SLOW_EMAS = [30, 40, 50]

RSI_PERIODS = [10, 14]

BUY_RSI_LEVELS = [55, 60]

SELL_RSI_LEVELS = [40, 45]