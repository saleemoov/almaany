# ELITE V9 Spot Trading Bot

Production-ready, modular, and secure OKX spot trading bot (Demo only).

## Features
- Multi-indicator, multi-timeframe strategy
- Full risk management and reporting
- Telegram alerts and commands
- SQLite database for all trades and stats
- Modular, well-documented code

## Setup
1. Copy `.env.example` to `.env` and fill in your credentials.
2. Install requirements: `pip install -r requirements.txt`
3. Run: `python main.py`

## Files
- `main.py`: Entry point
- `indicators.py`: Indicator calculations
- `confidence.py`: Confidence scoring
- `market_state.py`: Market detection
- `strategy.py`: Entry/exit logic
- `okx_client.py`: OKX API wrapper
- `telegram_bot.py`: Alerts and commands
- `risk_manager.py`: SL, cooldown, blacklist
- `logger.py`: Error logging
- `reports.py`: Daily/weekly/monthly reports
- `config.py`: Load .env variables
- `database.py`: SQLite operations

## Security
- Never commit `.env` or real credentials
- Demo mode only (no real trading)

## License
MIT
