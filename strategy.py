# strategy.py - Entry/exit logic for ELITE V9
from typing import Any, Dict
from datetime import datetime
import pandas as pd
from indicators import *
from confidence import calculate_confidence
from market_state import detect_market_state

class EliteV9Strategy:
    """
    Implements the main trading logic for ELITE V9:
    - Fetches data for all coins
    - Calculates indicators and confidence
    - Checks market state and risk
    - Places/cancels orders via OKXClient
    - Records all actions in DB
    """
    def __init__(self, config, okx, db, risk, telegram):
        self.config = config
        self.okx = okx
        self.db = db
        self.risk = risk
        self.telegram = telegram
        self.watchlist = config['WATCHLIST']
        self.position_size = config['POSITION_SIZE_USD']
        self.cooldown_bars = config['COOLDOWN_BARS']
        self.min_confidence = config['MIN_CONFIDENCE']
        self.max_open_positions = config['MAX_OPEN_POSITIONS']
        self.max_daily_trades = config['MAX_DAILY_TRADES']
        self.last_scan_summary = {'bull': 0, 'bear': 0, 'sideways': 0,
                                  'best_coin': '-', 'best_confidence': 0,
                                  'total_scanned': 0}

    def run(self):
        """Main trading loop: called every 30m on candle close."""
        from logger import get_logger
        log = get_logger("strategy")
        log.info(f"=== Strategy scan started: {len(self.watchlist)} coins ===")
        summary = {'bull': 0, 'bear': 0, 'sideways': 0,
                   'best_coin': '-', 'best_confidence': 0,
                   'total_scanned': 0}
        for coin in self.watchlist:
            symbol = f"{coin}/USDT"
            try:
                # 1. Fetch 30m OHLCV
                ohlcv = self.okx.get_ohlcv(symbol, '30m', 100)
                if not ohlcv or len(ohlcv) < 30:
                    log.warning(f"{coin}: insufficient OHLCV data ({len(ohlcv) if ohlcv else 0} candles)")
                    continue
                df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
                # 2. Fetch HTF for market state
                ohlcv_4h = self.okx.get_ohlcv(symbol, '4h', 60)
                ohlcv_1d = self.okx.get_ohlcv(symbol, '1d', 60)
                if not ohlcv_4h or not ohlcv_1d:
                    log.warning(f"{coin}: failed to fetch 4h/1d data")
                    continue
                df_4h = pd.DataFrame(ohlcv_4h, columns=df.columns)
                df_1d = pd.DataFrame(ohlcv_1d, columns=df.columns)
                market_state = detect_market_state(df_4h, df_1d)
                # Track market summary
                summary['total_scanned'] += 1
                if market_state == 'BULL':
                    summary['bull'] += 1
                elif market_state == 'BEAR':
                    summary['bear'] += 1
                else:
                    summary['sideways'] += 1
                # 3. Calculate confidence
                conf = calculate_confidence(df)
                confidence = conf['total']
                is_bottom = conf.get('is_bottom', 0)
                log.info(f"{coin}: confidence={confidence} market={market_state} is_bottom={is_bottom} breakdown={conf}")
                # Track best signal
                if confidence > summary['best_confidence']:
                    summary['best_confidence'] = confidence
                    summary['best_coin'] = coin
                # 4. Risk checks (cooldown, open positions, blacklist, etc.)
                if not self.risk.can_trade(coin, confidence, is_bottom, market_state):
                    log.info(f"{coin}: SKIPPED by risk manager (conf={confidence}, state={market_state})")
                    continue
                # 5. Entry logic
                if confidence >= self.min_confidence:
                    # Place order (demo)
                    entry_price = df['close'].iloc[-1]
                    qty = self.okx.round_quantity(symbol, self.position_size / entry_price)
                    order = self.okx.create_limit_buy(symbol, entry_price, qty)
                    if order:
                        # Record trade, send alert, update cooldown, etc.
                        self.db.insert_trade({
                            'trade_id': f"{datetime.utcnow().strftime('%Y%m%d')}_{coin}_{int(datetime.utcnow().timestamp())}",
                            'coin': coin,
                            'entry_price': entry_price,
                            'entry_time': datetime.utcnow().isoformat(),
                            'entry_confidence': confidence,
                            'market_state': market_state,
                            'quantity': qty,
                            'position_size_usd': self.position_size,
                            'status': 'OPEN',
                            'order_id': order.get('id',''),
                        })
                        self.telegram.send_signal_alert(coin, confidence, market_state, entry_price, qty)
                        self.risk.record_trade(coin)
                        log.info(f"{coin}: ORDER PLACED at {entry_price} qty={qty}")
                    else:
                        log.error(f"{coin}: order placement FAILED")
                # 6. Exit logic (to be implemented: TP/SL/close)
                # ...
            except Exception as e:
                log.error(f"{coin}: EXCEPTION in strategy loop: {e}", exc_info=True)
        self.last_scan_summary = summary
        log.info(f"=== Strategy scan complete: bull={summary['bull']} bear={summary['bear']} side={summary['sideways']} best={summary['best_coin']}({summary['best_confidence']}) ===")

    def health_check(self):
        # Health check logic (to be implemented)
        pass
