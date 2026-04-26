# database.py - SQLite operations for ELITE V9
import sqlite3
from typing import Any, Optional, Dict
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
        order_id TEXT
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
        conn.commit()
    log.info("Database initialized.")

# Example helper: insert trade

def insert_trade(trade: Dict[str, Any]) -> int:
    sql = '''INSERT INTO trades (trade_id, coin, entry_price, entry_time, entry_confidence, market_state, quantity, position_size_usd, status, order_id)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
    with get_connection() as conn:
        cursor = conn.execute(sql, (
            trade['trade_id'], trade['coin'], trade['entry_price'], trade['entry_time'],
            trade['entry_confidence'], trade['market_state'], trade['quantity'],
            trade['position_size_usd'], trade['status'], trade['order_id']
        ))
        conn.commit()
        return cursor.lastrowid

# Add more CRUD and stats methods as needed for the bot
