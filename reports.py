# reports.py - Daily/weekly/monthly reports for ELITE V9
from typing import Any
from datetime import datetime

class ReportManager:
    """
    Handles daily, weekly, and monthly reporting for ELITE V9.
    """
    def __init__(self, config, db, telegram):
        self.config = config
        self.db = db
        self.telegram = telegram

    def send_daily_report(self):
        import asyncio
        stats = self.db.get_daily_stats(datetime.utcnow().date())
        msg = self._format_daily(stats)
        asyncio.run(self.telegram._send(msg))

    def send_weekly_report(self):
        import asyncio
        stats = self.db.get_weekly_stats()
        msg = self._format_weekly(stats)
        asyncio.run(self.telegram._send(msg))

    def send_monthly_report(self):
        import asyncio
        stats = self.db.get_monthly_stats()
        msg = self._format_monthly(stats)
        asyncio.run(self.telegram._send(msg))

    def _format_daily(self, stats: dict) -> str:
        trades = stats.get('total_trades', 0)
        wins = stats.get('winning_trades', 0)
        pnl = stats.get('net_profit_usd', 0)
        wr = round(wins / trades * 100, 1) if trades else 0
        return f"📊 DAILY REPORT - {datetime.utcnow().strftime('%Y-%m-%d')}\n🔢 Trades: {trades}\n✅ Wins: {wins} ({wr}%)\n💰 PnL: ${pnl:.2f}"

    def _format_weekly(self, stats: dict) -> str:
        return f"📊 WEEKLY REPORT\n{stats}"

    def _format_monthly(self, stats: dict) -> str:
        return f"📊 MONTHLY REPORT\n{stats}"
