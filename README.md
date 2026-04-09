# Crypto Trading Bot

A fully automated crypto trading bot for OKX spot market that analyzes markets, detects trading opportunities, manages trades, and sends Telegram alerts.

## Features

- Market condition detection using EMA and price action
- Entry signal scoring based on EMA, RSI, volume, and news
- Automated trade management with TP/SL levels
- Telegram alerts for signals, status, emergencies, and reports
- Consecutive loss protection
- News filtering using CryptoPanic API

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   CRYPTOPANIC_API_TOKEN=your_cryptopanic_token
   ```

3. Run the bot:
   ```bash
   python main.py
   ```

## Configuration

All trading parameters are configurable in `config.py`. Key settings include:
- Coin list
- Trade size and limits
- TP/SL percentages
- Signal score thresholds
- Scan intervals

## Database

Trade history is stored in `trades.db` SQLite database.

## Logging

Logs are written to `bot.log` and console.

## Disclaimer

This is a demo implementation for educational purposes. Use at your own risk. The bot simulates trades and does not execute real orders.