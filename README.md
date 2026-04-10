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
   ```bash
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   CRYPTOPANIC_API_TOKEN=your_cryptopanic_token
   OKX_API_KEY=your_okx_sandbox_api_key
   OKX_SECRET=your_okx_sandbox_secret
   OKX_PASSWORD=your_okx_sandbox_passphrase
   ```

3. Run the bot:
   ```bash
   python main.py
   ```

## Deployment on DigitalOcean

Recommended deployment files are included: `run_bot.sh` and `almaany.service`.

1. Copy the repository to your droplet and place it in a stable directory, for example `/root/almaany`.
2. Create a Python virtual environment on the server:
   ```bash
   cd /root/almaany
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Configure `.env` with your sandbox OKX keys and Telegram credentials.
4. Run the bot manually for testing:
   ```bash
   ./run_bot.sh
   ```
5. To run it as a service, edit `almaany.service` and replace `/path/to/almaany` and `your_user_here` with your actual deployment path and user.
6. Install the systemd unit on the server:
   ```bash
   sudo cp almaany.service /etc/systemd/system/almaany.service
   sudo systemctl daemon-reload
   sudo systemctl enable almaany.service
   sudo systemctl start almaany.service
   sudo systemctl status almaany.service
   ```

> Keep `.env` private and do not commit it to version control.

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