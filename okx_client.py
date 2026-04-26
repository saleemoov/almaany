# okx_client.py - OKX API wrapper for ELITE V9
import ccxt
import time
from typing import Any, Dict, Optional
from logger import get_logger

class OKXClient:
    """
    Handles all OKX API interactions (demo only):
    - Market data fetching
    - Order execution (limit, market)
    - Precision/quantity rounding
    - Error handling & retries
    """
    def __init__(self, config: dict):
        self.config = config
        self.logger = get_logger("okx")
        self.demo_mode = config.get('OKX_DEMO_MODE', True)
        self.api_key = config['OKX_API_KEY']
        self.secret = config['OKX_SECRET_KEY']
        self.passphrase = config['OKX_PASSPHRASE']
        self.exchange = ccxt.okx({
            'apiKey': self.api_key,
            'secret': self.secret,
            'password': self.passphrase,
            'enableRateLimit': True,
            'headers': {'x-simulated-trading': '1'},
        })
        if not self.demo_mode:
            raise RuntimeError("OKXClient: DEMO MODE ONLY is enforced!")
        self.markets = self.exchange.load_markets()
        self.precision = self._get_precisions()

    def _get_precisions(self) -> Dict[str, int]:
        # Returns dict: {symbol: decimals}
        precisions = {}
        for symbol, m in self.markets.items():
            if symbol.endswith('/USDT'):
                precisions[symbol] = m['precision']['amount']
        return precisions

    def get_ohlcv(self, symbol: str, timeframe: str = '30m', limit: int = 100) -> Optional[list]:
        for attempt in range(3):
            try:
                return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            except Exception as e:
                self.logger.warning(f"OHLCV fetch failed ({symbol}, {timeframe}): {e}")
                time.sleep(5)
        self.logger.error(f"Failed to fetch OHLCV for {symbol} after 3 attempts.")
        return None

    def get_ticker(self, symbol: str) -> Optional[dict]:
        for attempt in range(3):
            try:
                return self.exchange.fetch_ticker(symbol)
            except Exception as e:
                self.logger.warning(f"Ticker fetch failed ({symbol}): {e}")
                time.sleep(5)
        self.logger.error(f"Failed to fetch ticker for {symbol} after 3 attempts.")
        return None

    def get_balance(self, asset: str = 'USDT') -> float:
        try:
            balance = self.exchange.fetch_balance()
            return float(balance['total'].get(asset, 0))
        except Exception as e:
            self.logger.error(f"Balance fetch failed: {e}")
            return 0.0

    def round_quantity(self, symbol: str, qty: float) -> float:
        # Rounds to OKX min precision for the symbol
        decimals = self.precision.get(symbol, 8)
        return float(f"{qty:.{decimals}f}")

    def create_limit_buy(self, symbol: str, price: float, qty: float) -> Optional[dict]:
        qty = self.round_quantity(symbol, qty)
        for attempt in range(3):
            try:
                order = self.exchange.create_limit_buy_order(symbol, qty, price)
                return order
            except Exception as e:
                self.logger.warning(f"Limit buy failed ({symbol}): {e}")
                time.sleep(5)
        self.logger.error(f"Failed to place limit buy for {symbol} after 3 attempts.")
        return None

    def create_limit_sell(self, symbol: str, price: float, qty: float) -> Optional[dict]:
        qty = self.round_quantity(symbol, qty)
        for attempt in range(3):
            try:
                order = self.exchange.create_limit_sell_order(symbol, qty, price)
                return order
            except Exception as e:
                self.logger.warning(f"Limit sell failed ({symbol}): {e}")
                time.sleep(5)
        self.logger.error(f"Failed to place limit sell for {symbol} after 3 attempts.")
        return None

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            self.exchange.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            self.logger.warning(f"Cancel order failed ({symbol}): {e}")
            return False
