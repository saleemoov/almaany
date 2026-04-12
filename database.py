import sqlite3
import sqlite3
from config import DB_FILE

class TradeDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.create_table()

    def create_table(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coin TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    profit_loss_pct REAL,
                    profit_loss_usd REAL,
                    result TEXT,
                    timestamp_open TEXT,
                    timestamp_close TEXT
                )
            ''')
        # Ensure all required columns exist (auto-migrate)
        required_columns = [
            ('result', 'TEXT'),
            ('profit_loss_pct', 'REAL'),
            ('profit_loss_usd', 'REAL'),
            ('timestamp_open', 'TEXT'),
            ('timestamp_close', 'TEXT'),
            ('exit_price', 'REAL')
        ]
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(trades)")
        existing_cols = [row[1] for row in cur.fetchall()]
        for col, coltype in required_columns:
            if col not in existing_cols:
                with self.conn:
                    self.conn.execute(f"ALTER TABLE trades ADD COLUMN {col} {coltype}")

    def save_trade(self, trade):
        with self.conn:
            cursor = self.conn.execute('''
                INSERT INTO trades (coin, entry_price, exit_price, profit_loss_pct, profit_loss_usd, result, timestamp_open, timestamp_close)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade['coin'], trade['entry_price'], trade.get('exit_price'), trade.get('profit_loss_pct'),
                trade.get('profit_loss_usd'), trade.get('result'), trade['timestamp_open'], trade.get('timestamp_close')
            ))
            return cursor.lastrowid

    def get_open_trades(self):
        with self.conn:
            rows = self.conn.execute("SELECT * FROM trades WHERE result IS NULL").fetchall()
            return [dict(zip([column[0] for column in self.conn.execute('PRAGMA table_info(trades)')], row)) for row in rows]

    def update_trade(self, trade_id, updates):
        with self.conn:
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [trade_id]
            self.conn.execute(f"UPDATE trades SET {set_clause} WHERE id = ?", values)

    def get_all_trades(self):
        with self.conn:
            rows = self.conn.execute("SELECT * FROM trades").fetchall()
            return [dict(zip([column[0] for column in self.conn.execute('PRAGMA table_info(trades)')], row)) for row in rows]

    def get_consecutive_losses(self):
        with self.conn:
            rows = self.conn.execute("SELECT result FROM trades WHERE result IS NOT NULL ORDER BY id DESC LIMIT 3").fetchall()
            return sum(1 for row in rows if row[0] == 'LOSS')
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