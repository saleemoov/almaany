# config.py - Load .env variables for ELITE V9
import os
from dotenv import load_dotenv

load_dotenv()

def load_config():
    config = {
        'OKX_API_KEY': os.getenv('OKX_API_KEY'),
        'OKX_SECRET_KEY': os.getenv('OKX_SECRET_KEY'),
        'OKX_PASSPHRASE': os.getenv('OKX_PASSPHRASE'),
        'OKX_DEMO_MODE': os.getenv('OKX_DEMO_MODE', 'true').lower() == 'true',
        'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
        'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID'),
        'POSITION_SIZE_USD': float(os.getenv('POSITION_SIZE_USD', 1000)),
        'STOP_LOSS_PERCENT': float(os.getenv('STOP_LOSS_PERCENT', 1.5)),
        'MAX_DAILY_TRADES': int(os.getenv('MAX_DAILY_TRADES', 4)),
        'MAX_OPEN_POSITIONS': int(os.getenv('MAX_OPEN_POSITIONS', 3)),
        'MAX_DAILY_LOSS_PERCENT': float(os.getenv('MAX_DAILY_LOSS_PERCENT', 5)),
        'COOLDOWN_BARS': int(os.getenv('COOLDOWN_BARS', 8)),
        'MIN_CONFIDENCE': int(os.getenv('MIN_CONFIDENCE', 50)),
        'INITIAL_CAPITAL': float(os.getenv('INITIAL_CAPITAL', 85000)),
        'WATCHLIST': [c.strip() for c in os.getenv(
            'WATCHLIST',
            'BTC,ETH,SOL,XRP,ADA,DOGE,LINK,SUI,AVAX,TRX,NEAR,APT,ATOM,FIL,'
            'BNB,DOT,LTC,BCH,TON,ETC,XLM,HBAR,OP,ARB,TAO'
        ).split(',') if c.strip()],
        'db_path': os.path.join(os.path.dirname(__file__), 'data', 'elite_v9.db'),
    }
    config['db'] = None  # Placeholder for db connection
    return config
