# telegram_bot.py - Telegram alerts and commands for ELITE V9
from typing import Any
from telegram import Bot
from logger import get_logger
from dotenv import load_dotenv
import os

load_dotenv()
DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'data', 'elite_v9.db'))

class TelegramBot:
    def __init__(self, config):
        self.config = config
        self.logger = get_logger("telegram")
        self.bot = Bot(token=config['TELEGRAM_BOT_TOKEN'])
        self.chat_id = config['TELEGRAM_CHAT_ID']

    def send_startup_alert(self):
        msg = "🤖 ELITE V9 BOT STARTING\n✅ OKX: Connected (Demo Mode)\n✅ Telegram: Connected\n✅ Watchlist: 25 coins\n⏰ Status: RUNNING"
        import asyncio
        asyncio.run(self._send(msg))

    def send_signal_alert(self, coin, confidence, market_state, entry_price, qty):
        msg = f"🔥 ELITE V9 - SIGNAL DETECTED! 🔥\n📈 COIN: #{coin}/USDT\n🎯 Confidence: {confidence}/100 💎\n📊 Market: {market_state}\n📉 Entry: ${entry_price:.2f}\n💰 Size: {qty}\n🚀 Decision: BUY NOW!"
        import asyncio
        asyncio.run(self._send(msg))

    def send_order_executed(self, coin, entry_price, qty, sl, tps):
        msg = f"✅ ORDER EXECUTED - BUY #{coin}/USDT\n💰 Entry: ${entry_price:.2f}\n📊 Size: {qty}\n🛡️ SL: ${sl:.2f}\n🎯 TP: {tps}\n⏰ Time: {self._now()}"
        import asyncio
        asyncio.run(self._send(msg))

    def send_tp_alert(self, coin, tp_label, price, profit):
        msg = (f"✅ TAKE PROFIT ACHIEVED! ✅\n"
               f"📈 COIN: #{coin}/USDT\n"
               f"💰 Exit: ${price:.4f}\n"
               f"📊 Profit: +${profit:.2f} (+2%)\n"
               f"🏆 Result: WIN")
        import asyncio
        asyncio.run(self._send(msg))

    def send_sl_alert(self, coin, price, loss, losses):
        msg = (f"🛑 STOP LOSS TRIGGERED 🛑\n"
               f"📉 COIN: #{coin}/USDT\n"
               f"💰 Exit: ${price:.4f}\n"
               f"📊 Loss: -${abs(loss):.2f} (-2%)\n"
               f"⚠️ Consecutive losses: {losses}/3")
        import asyncio
        asyncio.run(self._send(msg))

    def send_breakeven_alert(self, coin, entry_price):
        msg = (f"🛡️ BREAKEVEN ACTIVATED\n"
               f"📈 COIN: #{coin}/USDT\n"
               f"🔒 SL moved to entry: ${entry_price:.4f}\n"
               f"✅ Position now risk-free!")
        import asyncio
        asyncio.run(self._send(msg))

    def send_blacklist_alert(self, coin):
        msg = f"🚫 COIN BLACKLISTED 🚫\n📉 COIN: #{coin}/USDT\n⚠️ Reason: 3 consecutive losses\n⏸️ Duration: 7 days"
        import asyncio
        asyncio.run(self._send(msg))

    def send_emergency_stop(self, capital, loss_pct):
        msg = f"🛑🛑🛑 EMERGENCY STOP 🛑🛑🛑\n⚠️ Daily loss limit reached: {loss_pct:.2f}%\n💰 Capital: ${capital}\n⏸️ Bot paused for 24 hours"
        import asyncio
        asyncio.run(self._send(msg))

    def send_heartbeat(self, scan_summary: dict):
        """Sent every 6 hours: confirms bot is alive + market overview."""
        from datetime import datetime
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        bull   = scan_summary.get('bull', 0)
        bear   = scan_summary.get('bear', 0)
        side   = scan_summary.get('sideways', 0)
        best   = scan_summary.get('best_coin', '-')
        best_c = scan_summary.get('best_confidence', 0)
        scanned = scan_summary.get('total_scanned', 0)
        msg = (
            f"💓 ELITE V9 — HEARTBEAT\n"
            f"✅ Bot is running normally\n"
            f"⏰ Time: {now}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 MARKET OVERVIEW ({scanned} coins)\n"
            f"🐂 Bull: {bull} | 🐻 Bear: {bear} | ↔️ Sideways: {side}\n"
            f"🏆 Best signal: {best} ({best_c}/100)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ Mode: Demo | 🔒 OKX Connected"
        )
        import asyncio
        asyncio.run(self._send(msg))

    def send_status_report(self, status, trades, wins, pnl):
        msg = f"🤖 ELITE V9 BOT STATUS\n✅ Status: {status}\n📈 Today: {trades} trades | {wins} wins\n💰 Capital: ${pnl}"
        import asyncio
        asyncio.run(self._send(msg))

    async def _send(self, msg: str):
        try:
            # Create a fresh Bot instance each time to avoid stale event loop issues
            from telegram import Bot
            async with Bot(token=self.config['TELEGRAM_BOT_TOKEN']) as bot:
                await bot.send_message(chat_id=self.chat_id, text=msg)
        except Exception as e:
            self.logger.error(f"Telegram send failed: {e}")

    def _now(self):
        from datetime import datetime
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")