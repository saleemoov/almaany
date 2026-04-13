import sqlite3
import os
from datetime import datetime
from logger import get_logger

log = get_logger("database")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades.db")

CREATE_TRADES_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin TEXT NOT NULL,
    entry_price REAL NOT NULL,
    quantity REAL NOT NULL,
    tp1_price REAL,
    tp2_price REAL,
    tp3_price REAL,
    sl_price REAL,
    exit_price REAL,
    profit_loss_pct REAL,
    profit_loss_usd REAL,
    result TEXT,
    status TEXT DEFAULT 'open',
    sold_tp1 REAL DEFAULT 0,
    sold_tp2 REAL DEFAULT 0,
    entry_time TEXT,
    exit_time TEXT,
    order_id TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(CREATE_TRADES_SQL)
        conn.commit()
    log.info("Database initialized.")


def insert_trade(coin, entry_price, quantity, tp1, tp2, tp3, sl, order_id=None) -> int:
    sql = """
    INSERT INTO trades (coin, entry_price, quantity, tp1_price, tp2_price, tp3_price,
                        sl_price, status, entry_time, order_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
    """
    with get_connection() as conn:
        cursor = conn.execute(
            sql,
            (coin, entry_price, quantity, tp1, tp2, tp3, sl,
             datetime.utcnow().isoformat(), order_id),
        )
        conn.commit()
        return cursor.lastrowid


def get_open_trades() -> list:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM trades WHERE status='open'").fetchall()
    return [dict(r) for r in rows]


def get_open_trades_count() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM trades WHERE status='open'").fetchone()
    return row[0]


def update_trade_tp1(trade_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE trades SET sold_tp1=1 WHERE id=?", (trade_id,))
        conn.commit()


def update_trade_tp2(trade_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE trades SET sold_tp2=1 WHERE id=?", (trade_id,))
        conn.commit()


def close_trade(trade_id: int, exit_price: float, pnl_pct: float, pnl_usd: float, result: str):
    sql = """
    UPDATE trades
    SET status='closed', exit_price=?, profit_loss_pct=?, profit_loss_usd=?,
        result=?, exit_time=?
    WHERE id=?
    """
    with get_connection() as conn:
        conn.execute(
            sql,
            (exit_price, pnl_pct, pnl_usd, result, datetime.utcnow().isoformat(), trade_id),
        )
        conn.commit()


def get_daily_loss_usd() -> float:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(profit_loss_usd), 0) FROM trades "
            "WHERE status='closed' AND result='loss' AND entry_time LIKE ?",
            (f"{today}%",),
        ).fetchone()
    return abs(row[0]) if row[0] else 0.0


def get_weekly_loss_usd() -> float:
    from datetime import timedelta
    today = datetime.utcnow()
    monday = today - timedelta(days=today.weekday())
    monday_str = monday.strftime("%Y-%m-%d")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(profit_loss_usd), 0) FROM trades "
            "WHERE status='closed' AND result='loss' AND entry_time >= ?",
            (monday_str,),
        ).fetchone()
    return abs(row[0]) if row[0] else 0.0


def get_weekly_stats() -> dict:
    from datetime import timedelta
    today = datetime.utcnow()
    monday = today - timedelta(days=today.weekday())
    monday_str = monday.strftime("%Y-%m-%d")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM trades WHERE status='closed' AND entry_time >= ?",
            (monday_str,),
        ).fetchall()
    trades = [dict(r) for r in rows]
    wins = [t for t in trades if t["result"] == "win"]
    losses = [t for t in trades if t["result"] == "loss"]
    total_pnl = sum(t["profit_loss_usd"] or 0 for t in trades)

    best_coin = max(trades, key=lambda t: t["profit_loss_usd"] or 0, default=None)
    worst_coin = min(trades, key=lambda t: t["profit_loss_usd"] or 0, default=None)

    return {
        "total": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "pnl": round(total_pnl, 2),
        "best": best_coin["coin"] if best_coin else "—",
        "worst": worst_coin["coin"] if worst_coin else "—",
    }


def get_signals_since(since: datetime) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE entry_time >= ?",
            (since.isoformat(),),
        ).fetchone()
    return row[0]
