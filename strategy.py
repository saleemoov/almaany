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

        # ── EXIT LOGIC: check all open positions first ──────────────────────
        try:
            open_trades = self.db.get_open_trades()
            for trade in open_trades:
                coin       = trade['coin']
                symbol     = f"{coin}/USDT"
                entry      = float(trade['entry_price'])
                qty        = float(trade['quantity'])
                trade_id   = trade['trade_id']
                sl_price   = float(trade['stop_loss_price'])  # dynamic SL (moves to breakeven)
                try:
                    ticker = self.okx.get_ticker(symbol)
                    if not ticker:
                        continue
                    current = float(ticker['last'])
                    tp_price = entry * 1.02       # +2%
                    be_price = entry * 1.015      # +1.5% → breakeven trigger
                    initial_sl = entry * 0.98     # -2%

                    # 1. TAKE PROFIT
                    if current >= tp_price:
                        order = self.okx.create_limit_sell(symbol, current, qty)
                        if order:
                            self.db.close_trade(trade_id, current, 'TP')
                            profit = (current - entry) * qty
                            self.telegram.send_tp_alert(coin, 'TP +2%', current, profit)
                            self.risk.record_exit(coin, profit, was_loss=False)
                            log.info(f"{coin}: TP HIT at {current} profit=${profit:.2f}")

                    # 2. STOP LOSS (uses dynamic SL which may be at entry after breakeven)
                    elif current <= sl_price:
                        order = self.okx.create_limit_sell(symbol, current, qty)
                        if order:
                            self.db.close_trade(trade_id, current, 'SL')
                            loss = (current - entry) * qty
                            losses = self.db.get_consecutive_losses(coin)
                            self.telegram.send_sl_alert(coin, current, loss, losses)
                            self.risk.record_exit(coin, loss, was_loss=(loss < 0))
                            log.info(f"{coin}: SL HIT at {current} loss=${loss:.2f}")

                    # 3. BREAKEVEN: move SL to entry when up 1.5%
                    elif current >= be_price and abs(sl_price - initial_sl) < 0.000001:
                        self.db.update_stop_loss(trade_id, entry)
                        self.telegram.send_breakeven_alert(coin, entry)
                        log.info(f"{coin}: BREAKEVEN activated, SL moved to {entry}")

                except Exception as e:
                    log.error(f"{coin}: EXCEPTION in exit check: {e}", exc_info=True)
        except Exception as e:
            log.error(f"Exit loop EXCEPTION: {e}", exc_info=True)

        # ── ENTRY LOGIC: scan for new signals ───────────────────────────────
        for coin in self.watchlist:
            symbol = f"{coin}/USDT"
            try:
                # Duplicate protection: skip if already open
                if self.db.is_coin_open(coin):
                    log.info(f"⚠️ {coin} already has open position - SKIPPED")
                    continue

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
                # 4. Risk checks
                if not self.risk.can_trade(coin, confidence, is_bottom, market_state):
                    log.info(f"{coin}: SKIPPED by risk manager (conf={confidence}, state={market_state})")
                    continue
                # 5. Entry logic
                if confidence >= self.min_confidence:
                    entry_price = df['close'].iloc[-1]
                    qty = self.okx.round_quantity(symbol, self.position_size / entry_price)
                    order = self.okx.create_limit_buy(symbol, entry_price, qty)
                    if order:
                        sl_price = round(entry_price * 0.98, 8)
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
                            'stop_loss_price': sl_price,
                        })
                        self.telegram.send_signal_alert(coin, confidence, market_state, entry_price, qty)
                        self.risk.record_trade(coin)
                        log.info(f"{coin}: ORDER PLACED at {entry_price} qty={qty} SL={sl_price} order_id={order.get('id','?')}")
                    else:
                        log.error(f"{coin}: order placement FAILED")
            except Exception as e:
                log.error(f"{coin}: EXCEPTION in entry loop: {e}", exc_info=True)

        self.last_scan_summary = summary
        log.info(f"=== Strategy scan complete: bull={summary['bull']} bear={summary['bear']} side={summary['sideways']} best={summary['best_coin']}({summary['best_confidence']}) ===")

    def health_check(self):
        # Health check logic (to be implemented)
        pass
