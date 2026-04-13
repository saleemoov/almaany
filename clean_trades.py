import sqlite3
from config import DB_FILE

# List of required columns for a valid trade row
REQUIRED_KEYS = [
    'coin', 'entry_price', 'tp1_price', 'tp2_price', 'tp3_price', 'sl_price', 'quantity', 'entry_time', 'order_id'
]

def clean_trades():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    # Get all columns in the table
    cur.execute('PRAGMA table_info(trades)')
    columns = [row[1] for row in cur.fetchall()]
    # Get all trades
    cur.execute('SELECT * FROM trades')
    trades = cur.fetchall()
    # Find invalid rows (missing required keys or None values)
    invalid_ids = []
    for trade in trades:
        trade_dict = dict(zip(columns, trade))
        if any(k not in trade_dict or trade_dict[k] is None for k in ['coin']):
            invalid_ids.append(trade_dict.get('id'))
    # Delete invalid rows
    if invalid_ids:
        cur.executemany('DELETE FROM trades WHERE id = ?', [(i,) for i in invalid_ids if i is not None])
        print(f"Deleted {len(invalid_ids)} invalid trades.")
    else:
        print("No invalid trades found.")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    clean_trades()
