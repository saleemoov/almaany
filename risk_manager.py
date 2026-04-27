# risk_manager.py - Risk, SL, cooldown, blacklist for ELITE V9
from typing import Any, Dict
from datetime import datetime, timedelta

class RiskManager:
    """
    Handles all risk checks: cooldown, open positions, daily trades, blacklist, emergency stop.
    """
    def __init__(self, config, db, telegram):
        self.config = config
        self.db = db
        self.telegram = telegram
        self.cooldowns = {}  # coin: last_trade_time
        self.blacklist = {}  # coin: blacklist_until
        self.daily_trades = 0
        self.open_positions = 0
        self.daily_loss = 0.0
        self.last_reset = datetime.utcnow().date()

    def can_trade(self, coin: str, confidence: int, is_bottom: int, market_state: str) -> bool:
        now = datetime.utcnow()
        self._reset_if_new_day(now)
        # Blacklist check
        if coin in self.blacklist and self.blacklist[coin] > now:
            return False
        # Cooldown check
        if coin in self.cooldowns and (now - self.cooldowns[coin]).total_seconds() < self.config['COOLDOWN_BARS'] * 30 * 60:
            return False
        # Open positions
        if self.open_positions >= self.config['MAX_OPEN_POSITIONS']:
            return False
        # Daily trades
        if self.daily_trades >= self.config['MAX_DAILY_TRADES']:
            return False
        # Emergency stop
        if self.daily_loss >= self.config['INITIAL_CAPITAL'] * self.config['MAX_DAILY_LOSS_PERCENT'] / 100:
            return False
        # Market state rules
        if market_state == 'BULL' and confidence >= self.config['MIN_CONFIDENCE']:
            return True
        if market_state in ('SIDEWAYS', 'BEAR') and confidence >= 80 and is_bottom:
            return True
        return False

    def record_trade(self, coin: str):
        now = datetime.utcnow()
        self.cooldowns[coin] = now
        self.daily_trades += 1
        self.open_positions += 1

    def record_exit(self, coin: str, pnl: float, was_loss: bool):
        self.open_positions = max(0, self.open_positions - 1)
        if was_loss:
            self.daily_loss += abs(pnl)
            # Blacklist logic
            losses = self.db.get_consecutive_losses(coin)
            if losses >= 3:
                self.blacklist[coin] = datetime.utcnow() + timedelta(days=7)
                self.telegram.send_blacklist_alert(coin)

    def _reset_if_new_day(self, now):
        if now.date() != self.last_reset:
            self.daily_trades = 0
            self.open_positions = 0
            self.daily_loss = 0.0
            self.last_reset = now.date()
