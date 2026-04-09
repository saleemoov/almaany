import sqlite3
import json
from datetime import datetime
from config import DB_FILE, MAX_CONSECUTIVE_LOSSES

class TradeDatabase:
    def __init__(self):
        self.db_file = DB_FILE
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coin TEXT,
                    entry_price REAL,
                    quantity REAL,
                    entry_time TEXT,
                    tp1_price REAL,
                    tp2_price REAL,
                    tp3_price REAL,
                    sl_price REAL,
                    status TEXT,  -- open, closed
                    exit_price REAL,
                    exit_time TEXT,
                    pnl REAL,
                    pnl_percentage REAL,
                    result TEXT,  -- WIN, LOSS
                    sold_tp1 REAL DEFAULT 0,
                    sold_tp2 REAL DEFAULT 0,
                    sold_tp3 REAL DEFAULT 0,
                    order_id TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            conn.commit()

    def save_trade(self, trade):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (coin, entry_price, quantity, entry_time, tp1_price, tp2_price, tp3_price, sl_price, order_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
            ''', (
                trade['coin'], trade['entry_price'], trade['quantity'], trade['entry_time'],
                trade['tp1_price'], trade['tp2_price'], trade['tp3_price'], trade['sl_price'], trade.get('order_id', '')
            ))
            conn.commit()
            return cursor.lastrowid

    def update_trade(self, trade_id, updates):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [trade_id]
            cursor.execute(f'UPDATE trades SET {set_clause} WHERE id = ?', values)
            conn.commit()

    def get_open_trades(self):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trades WHERE status = "open"')
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_all_trades(self):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trades ORDER BY entry_time DESC')
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_consecutive_losses(self):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT result FROM trades WHERE status = "closed" ORDER BY exit_time DESC LIMIT ?', (MAX_CONSECUTIVE_LOSSES,))
            results = [row[0] for row in cursor.fetchall()]
            consecutive_losses = 0
            for result in results:  # most recent first
                if result == 'LOSS':
                    consecutive_losses += 1
                else:
                    break
            return consecutive_losses

    def set_bot_state(self, key, value):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO bot_state (key, value) VALUES (?, ?)', (key, json.dumps(value)))
            conn.commit()

    def get_bot_state(self, key):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM bot_state WHERE key = ?', (key,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None