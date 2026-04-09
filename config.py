import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your_telegram_bot_token")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "your_chat_id")

# API Tokens
CRYPTOPANIC_API_TOKEN = os.getenv("CRYPTOPANIC_API_TOKEN", "your_cryptopanic_token")

# OKX Configuration
OKX_BASE_URL = "https://www.okx.com"
OKX_API_KEY = os.getenv("OKX_API_KEY", "")
OKX_SECRET = os.getenv("OKX_SECRET", "")
OKX_PASSWORD = os.getenv("OKX_PASSWORD", "")

# Trading Parameters
TRADE_SIZE_USD = 1000
MAX_OPEN_TRADES = 3
STOP_LOSS_PCT = 0.02
TP1_PCT = 0.015
TP2_PCT = 0.030
TP3_PCT = 0.045
TP1_SELL_PCT = 0.40
TP2_SELL_PCT = 0.40
TP3_SELL_PCT = 0.20
MIN_SIGNAL_SCORE = 75
MAX_CONSECUTIVE_LOSSES = 3
PAUSE_HOURS = 24
SCAN_INTERVAL_MINUTES = 15
EMERGENCY_DROP_PCT = 0.10
EMERGENCY_TIMEFRAME_MINUTES = 60

# Coin List
COINS = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "AVAX", "DOT", "ATOM", "DOGE"]

# Timeframes
TIMEFRAME_4H = "4H"
TIMEFRAME_1H = "1H"
TIMEFRAME_1M = "1m"

# Candles count
CANDLES_COUNT = 50

# EMA periods
EMA21_PERIOD = 21
EMA50_PERIOD = 50

# RSI period
RSI_PERIOD = 14

# Volume average period
VOLUME_AVG_PERIOD = 20

# Support/Resistance period
SR_PERIOD = 20

# Sideways EMA threshold (for EMA21 ≈ EMA50)
EMA_THRESHOLD = 0.005  # 0.5%

# Sideways entry price threshold above support
SIDEWAYS_ENTRY_THRESHOLD = 0.015  # 1.5%

# Sideways RSI max
SIDEWAYS_RSI_MAX = 45

# News check hours
NEWS_CHECK_HOURS = 4

# Database file
DB_FILE = "trades.db"

# Log file
LOG_FILE = "bot.log"