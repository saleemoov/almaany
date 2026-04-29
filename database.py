# database.py - SQLite operations for ELITE V9
import sqlite3
from typing import Any, Optional, Dict
from datetime import datetime
import os
from logger import get_logger

log = get_logger('database')

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'elite_v9.db')

SCHEMA = [
    # trades table
    '''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id TEXT UNIQUE,
        coin TEXT,
        entry_price REAL,
        entry_time TEXT,
        entry_confidence INTEGER,
        market_state TEXT,
        exit_price REAL,
        exit_time TEXT,
        exit_reason TEXT,
        quantity REAL,
        position_size_usd REAL,
        gross_profit_usd REAL,
        fees_paid REAL,
        net_profit_usd REAL,
        net_profit_percent REAL,
        status TEXT,
        order_id TEXT,
        stop_loss_price REAL
    );''',
    # daily_stats table
    '''CREATE TABLE IF NOT EXISTS daily_stats (
        date TEXT PRIMARY KEY,
        total_trades INTEGER,
        winning_trades INTEGER,
        losing_trades INTEGER,
        win_rate REAL,
        gross_profit_usd REAL,
        fees_paid REAL,
        net_profit_usd REAL,
        net_profit_percent REAL,
        best_trade REAL,
        worst_trade REAL,
        starting_balance REAL,
        ending_balance REAL
    );''',
    # coin_stats table
    '''CREATE TABLE IF NOT EXISTS coin_stats (
        coin TEXT PRIMARY KEY,
        total_trades INTEGER,
        winning_trades INTEGER,
        consecutive_losses INTEGER,
        is_blacklisted INTEGER,
        blacklist_until TEXT,
        last_trade_time TEXT,
        net_profit_usd REAL,
        win_rate REAL
    );''',
    # alerts_sent table
    '''CREATE TABLE IF NOT EXISTS alerts_sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT,
        coin TEXT,
        message TEXT,
        status TEXT,
        sent_at TEXT
    );''',
    # signals_history table
    '''CREATE TABLE IF NOT EXISTS signals_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT,
        confidence INTEGER,
        market_state TEXT,
        signal_time TEXT,
        rsi REAL,
        stoch_k REAL,
        adx REAL,
        volume_ratio REAL,
        was_traded INTEGER
    );'''
]

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        for stmt in SCHEMA:
            conn.execute(stmt)
        # Add stop_loss_price column if upgrading from old DB
        try:
            conn.execute('ALTER TABLE trades ADD COLUMN stop_loss_price REAL')
        except Exception:
            pass  # Column already exists
        conn.commit()
    log.info("Database initialized.")

# Example helper: insert trade

def insert_trade(trade: Dict[str, Any]) -> int:
    sql = '''INSERT INTO trades (trade_id, coin, entry_price, entry_time, entry_confidence,
                                 market_state, quantity, position_size_usd, status, order_id, stop_loss_price)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
    with get_connection() as conn:
        cursor = conn.execute(sql, (
            trade['trade_id'], trade['coin'], trade['entry_price'], trade['entry_time'],
            trade['entry_confidence'], trade['market_state'], trade['quantity'],
            trade['position_size_usd'], trade['status'], trade['order_id'],
            trade.get('stop_loss_price', trade['entry_price'] * 0.98)
        ))
        conn.commit()
        return cursor.lastrowid

def get_daily_stats(date) -> dict:
    sql = '''SELECT COUNT(*) as total_trades,
                    SUM(CASE WHEN net_profit_usd > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN net_profit_usd <= 0 THEN 1 ELSE 0 END) as losing_trades,
                    COALESCE(SUM(net_profit_usd), 0) as net_profit_usd
             FROM trades WHERE DATE(entry_time) = ?'''
    with get_connection() as conn:
        row = conn.execute(sql, (str(date),)).fetchone()
        return dict(row) if row else {}

def get_weekly_stats() -> dict:
    sql = '''SELECT COUNT(*) as total_trades,
                    SUM(CASE WHEN net_profit_usd > 0 THEN 1 ELSE 0 END) as winning_trades,
                    COALESCE(SUM(net_profit_usd), 0) as net_profit_usd
             FROM trades WHERE entry_time >= DATE('now', '-7 days')'''
    with get_connection() as conn:
        row = conn.execute(sql).fetchone()
        return dict(row) if row else {}

def get_monthly_stats() -> dict:
    sql = '''SELECT COUNT(*) as total_trades,
                    SUM(CASE WHEN net_profit_usd > 0 THEN 1 ELSE 0 END) as winning_trades,
                    COALESCE(SUM(net_profit_usd), 0) as net_profit_usd
             FROM trades WHERE entry_time >= DATE('now', '-30 days')'''
    with get_connection() as conn:
        row = conn.execute(sql).fetchone()
        return dict(row) if row else {}

def get_consecutive_losses(coin: str) -> int:
    sql = '''SELECT COUNT(*) as cnt FROM (
                SELECT net_profit_usd FROM trades
                WHERE coin = ? ORDER BY entry_time DESC LIMIT 3
             ) WHERE net_profit_usd < 0'''
    with get_connection() as conn:
        row = conn.execute(sql, (coin,)).fetchone()
        return row['cnt'] if row else 0

def get_open_trades() -> list:
    """Returns all trades with status=OPEN as list of dicts."""
    sql = '''SELECT trade_id, coin, entry_price, quantity, position_size_usd, order_id,
                    COALESCE(stop_loss_price, entry_price * 0.98) as stop_loss_price
             FROM trades WHERE status = 'OPEN' '''
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

def close_trade(trade_id: str, exit_price: float, exit_reason: str) -> None:
    """Closes a trade: calculates PnL and updates record."""
    with get_connection() as conn:
        row = conn.execute(
            'SELECT entry_price, quantity, position_size_usd FROM trades WHERE trade_id = ?',
            (trade_id,)
        ).fetchone()
        if not row:
            return
        entry_price = row['entry_price']
        quantity = row['quantity']
        position_size_usd = row['position_size_usd']
        gross_profit = (exit_price - entry_price) * quantity
        fees = (position_size_usd + abs(gross_profit)) * 0.001  # 0.1% fee estimate
        net_profit = gross_profit - fees
        net_pct = (net_profit / position_size_usd) * 100 if position_size_usd else 0
        conn.execute('''UPDATE trades SET
            exit_price = ?, exit_time = ?, exit_reason = ?,
            gross_profit_usd = ?, fees_paid = ?, net_profit_usd = ?,
            net_profit_percent = ?, status = ?
            WHERE trade_id = ?''', (
            exit_price, datetime.utcnow().isoformat(), exit_reason,
            round(gross_profit, 4), round(fees, 4), round(net_profit, 4),
            round(net_pct, 4), 'CLOSED', trade_id
        ))
        conn.commit()

def update_stop_loss(trade_id: str, new_sl: float) -> None:
    """Updates the stop loss price for a trade (breakeven protection)."""
    with get_connection() as conn:
        conn.execute('UPDATE trades SET stop_loss_price = ? WHERE trade_id = ?',
                     (new_sl, trade_id))
        conn.commit()

def is_coin_open(coin: str) -> bool:
    """Returns True if coin already has an OPEN position."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM trades WHERE coin = ? AND status = 'OPEN' LIMIT 1", (coin,)
        ).fetchone()
        return row is not None
