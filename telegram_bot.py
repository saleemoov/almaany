# telegram_bot.py - Telegram alerts and commands for ELITE V9
from typing import Any
from python_telegram_bot import Bot
from logger import get_logger

class TelegramBot:
    """
    Handles all Telegram alerts and commands for ELITE V9.
    """
    def __init__(self, config):
        self.config = config
        self.logger = get_logger("telegram")
        self.bot = Bot(token=config['TELEGRAM_BOT_TOKEN'])
        self.chat_id = config['TELEGRAM_CHAT_ID']

    def send_startup_alert(self):
        msg = "🤖 ELITE V9 BOT STARTING\n✅ OKX: Connected (Demo Mode)\n✅ Telegram: Connected\n✅ Watchlist: 14 coins\n⏰ Status: RUNNING"
        self._send(msg)

    def send_signal_alert(self, coin, confidence, market_state, entry_price, qty):
        msg = f"🔥 ELITE V9 - SIGNAL DETECTED! 🔥\n📈 COIN: #{coin}/USDT\n🎯 Confidence: {confidence}/100 💎\n📊 Market: {market_state}\n📉 Entry: ${entry_price:.2f}\n💰 Size: {qty}\n🚀 Decision: BUY NOW!"
        self._send(msg)

    def send_order_executed(self, coin, entry_price, qty, sl, tps):
        msg = f"✅ ORDER EXECUTED - BUY #{coin}/USDT\n💰 Entry: ${entry_price:.2f}\n📊 Size: {qty}\n🛡️ SL: ${sl:.2f}\n🎯 TP: {tps}\n⏰ Time: {self._now()}"
        self._send(msg)

    def send_tp_alert(self, coin, tp_label, price, profit):
        msg = f"🎯 {tp_label} ACHIEVED! 🎯\n📈 COIN: #{coin}/USDT\n💰 Exit: ${price:.2f}\n📊 Profit: +${profit:.2f}"
        self._send(msg)

    def send_sl_alert(self, coin, price, loss, losses):
        msg = f"🛑 STOP LOSS TRIGGERED 🛑\n📉 COIN: #{coin}/USDT\n💰 Exit: ${price:.2f}\n📊 Loss: -${loss:.2f}\n⚠️ Consecutive losses: {losses}/3"
        self._send(msg)

    def send_blacklist_alert(self, coin):
        msg = f"🚫 COIN BLACKLISTED 🚫\n📉 COIN: #{coin}/USDT\n⚠️ Reason: 3 consecutive losses\n⏸️ Duration: 7 days"
        self._send(msg)

    def send_emergency_stop(self, capital, loss_pct):
        msg = f"🛑🛑🛑 EMERGENCY STOP 🛑🛑🛑\n⚠️ Daily loss limit reached: {loss_pct:.2f}%\n💰 Capital: ${capital}\n⏸️ Bot paused for 24 hours"
        self._send(msg)

    def send_status_report(self, status, trades, wins, pnl):
        msg = f"🤖 ELITE V9 BOT STATUS\n✅ Status: {status}\n📈 Today: {trades} trades | {wins} wins\n💰 Capital: ${pnl}"
        self._send(msg)

    def _send(self, msg: str):
        try:
            self.bot.send_message(chat_id=self.chat_id, text=msg)
        except Exception as e:
            self.logger.error(f"Telegram send failed: {e}")

    def _now(self):
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
