import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from market_analyzer import MarketAnalyzer
from telegram_bot import TelegramBot
from database import TradeDatabase
from config import (
    COINS, SCAN_INTERVAL_MINUTES, TRADE_SIZE_USD, MAX_OPEN_TRADES,
    TP1_PCT, TP2_PCT, TP3_PCT, STOP_LOSS_PCT, TP1_SELL_PCT, TP2_SELL_PCT, TP3_SELL_PCT,
    MIN_SIGNAL_SCORE, MAX_CONSECUTIVE_LOSSES, PAUSE_HOURS, SR_PERIOD,
    OKX_API_KEY, OKX_SECRET, OKX_PASSWORD
)
from logger import logger
import ccxt.async_support as ccxt

class TradingBot:
    def __init__(self):
        self.analyzer = MarketAnalyzer()
        self.telegram = TelegramBot()
        self.db = TradeDatabase()
        self.scheduler = AsyncIOScheduler()
        self.paused_until = None
        self.last_status_report = datetime.utcnow()
        self.opportunities_since_report = 0
        # Initialize OKX exchange for demo trading
        self.exchange = ccxt.okx({
            'apiKey': OKX_API_KEY,
            'secret': OKX_SECRET,
            'password': OKX_PASSWORD,
            'sandbox': True,  # Demo mode
            'enableRateLimit': True,
            'headers': {'x-simulated-trading': '1'}  # Demo environment header
        })

    async def start(self):
        logger.info("Starting trading bot")
        # Schedule main scan every 15 minutes
        self.scheduler.add_job(self.scan_coins, 'interval', minutes=SCAN_INTERVAL_MINUTES)
        # Status report every 12 hours
        self.scheduler.add_job(self.send_status_report, 'interval', hours=12)
        # Weekly report every Sunday at 08:00 UTC
        self.scheduler.add_job(self.send_weekly_report, CronTrigger(day_of_week='sun', hour=8))
        self.scheduler.start()
        # Run initial scan
        await self.scan_coins()
        # Keep running
        while True:
            await asyncio.sleep(60)

    async def scan_coins(self):
        if self.is_paused():
            logger.info("Bot is paused")
            return

        logger.info("Scanning coins")
        open_trades = self.db.get_open_trades()
        if len(open_trades) >= MAX_OPEN_TRADES:
            logger.info("Max open trades reached")
            return

        for coin in COINS:
            await self.process_coin(coin, open_trades)

        # Check emergency drops
        await self.check_emergency_drops()

        # Update open trades
        await self.update_open_trades()

    async def process_coin(self, coin, open_trades):
        logger.info(f"Scanning coin: {coin}")
        # Step 1: Market condition on 4H
        df_4h = self.analyzer.fetch_candles(coin, '4H')
        if df_4h is None:
            return
        df_4h = self.analyzer.calculate_indicators(df_4h)
        condition = self.analyzer.get_market_condition(df_4h)
        logger.info(f"Market condition for {coin}: {condition}")
        if condition == 'TRENDING_DOWN':
            return

        support = df_4h['low'].tail(SR_PERIOD).min()

        # Step 2: Entry signal on 1H
        df_1h = self.analyzer.fetch_candles(coin, '1H')
        if df_1h is None:
            return
        df_1h = self.analyzer.calculate_indicators(df_1h)
        score = self.analyzer.calculate_signal_score(df_1h, condition, support, coin)
        logger.info(f"Signal score for {coin}: {score}")

        if score >= MIN_SIGNAL_SCORE and len(open_trades) < MAX_OPEN_TRADES:
            await self.create_trade(coin, df_1h.iloc[-1]['close'], score, condition, self.analyzer.check_negative_news(coin))
            self.opportunities_since_report += 1

    async def create_trade(self, coin, entry_price, score, condition, news_good):
        quantity = TRADE_SIZE_USD / entry_price
        tp1 = entry_price * (1 + TP1_PCT)
        tp2 = entry_price * (1 + TP2_PCT)
        tp3 = entry_price * (1 + TP3_PCT)
        sl = entry_price * (1 - STOP_LOSS_PCT)
        entry_time = datetime.utcnow().isoformat()

        # Send buy order on demo account
        symbol = f'{coin}/USDT'
        try:
            order = await self.exchange.create_market_buy_order(symbol, quantity)
            order_id = order['id']
            logger.info(f"Placed demo buy order for {coin}: {order}")
        except Exception as e:
            logger.error(f"Failed to place demo buy order for {coin}: {e}")
            return

        trade = {
            'coin': coin,
            'entry_price': entry_price,
            'quantity': quantity,
            'entry_time': entry_time,
            'tp1_price': tp1,
            'tp2_price': tp2,
            'tp3_price': tp3,
            'sl_price': sl,
            'order_id': order_id
        }
        trade_id = self.db.save_trade(trade)
        logger.info(f"Created demo trade for {coin} at {entry_price}")

        # Send Telegram alert for signal
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        await self.telegram.send_signal_alert(coin, condition, score, entry_price, tp1, tp2, tp3, sl, news_good, timestamp)
        
        # Send Telegram alert for buy execution
        await self.telegram.send_buy_execution(coin, entry_price, quantity, tp1, tp2, tp3, sl, timestamp)

    async def update_open_trades(self):
        open_trades = self.db.get_open_trades()
        for trade in open_trades:
            current_price = self.analyzer.get_current_price(trade['coin'])
            if current_price is None:
                continue

            # Check SL
            if current_price <= trade['sl_price']:
                await self.close_trade(trade, current_price, 'SL')
                continue

            # Check TP levels
            remaining_qty = trade['quantity'] * (1 - trade.get('sold_tp1', 0) - trade.get('sold_tp2', 0) - trade.get('sold_tp3', 0))
            if current_price >= trade['tp1_price'] and trade.get('sold_tp1', 0) == 0:
                sell_qty = trade['quantity'] * TP1_SELL_PCT
                await self.partial_close_trade(trade, sell_qty, current_price, 'TP1')
                # Move SL to breakeven
                self.db.update_trade(trade['id'], {'sl_price': trade['entry_price']})
            if current_price >= trade['tp2_price'] and trade.get('sold_tp2', 0) == 0:
                sell_qty = trade['quantity'] * TP2_SELL_PCT
                await self.partial_close_trade(trade, sell_qty, current_price, 'TP2')
            if current_price >= trade['tp3_price'] and trade.get('sold_tp3', 0) == 0:
                sell_qty = remaining_qty
                await self.close_trade(trade, current_price, 'TP3')

    async def partial_close_trade(self, trade, sell_qty, price, reason):
        # Send sell order
        symbol = f"{trade['coin']}/USDT"
        try:
            order = await self.exchange.create_market_sell_order(symbol, sell_qty)
            logger.info(f"Partial close {trade['coin']} {sell_qty} at {price} ({reason})")
        except Exception as e:
            logger.error(f"Failed to partial close {trade['coin']}: {e}")
            return

        # Calculate profit percentage
        profit_pct = ((price - trade['entry_price']) / trade['entry_price']) * 100
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Send Telegram alert for TP hit
        await self.telegram.send_tp_hit(trade['coin'], reason, price, profit_pct, timestamp)

        # Update sold amounts
        if reason == 'TP1':
            self.db.update_trade(trade['id'], {'sold_tp1': TP1_SELL_PCT})
        elif reason == 'TP2':
            self.db.update_trade(trade['id'], {'sold_tp2': TP2_SELL_PCT})

    async def close_trade(self, trade, price, reason):
        # Send sell order for remaining quantity
        remaining_qty = trade['quantity'] * (1 - trade.get('sold_tp1', 0) - trade.get('sold_tp2', 0) - trade.get('sold_tp3', 0))
        if remaining_qty > 0:
            symbol = f"{trade['coin']}/USDT"
            try:
                order = await self.exchange.create_market_sell_order(symbol, remaining_qty)
                logger.info(f"Closed trade {trade['coin']} at {price} ({reason})")
            except Exception as e:
                logger.error(f"Failed to close trade {trade['coin']}: {e}")
                return

        pnl = (price - trade['entry_price']) * trade['quantity']
        pnl_percentage = ((price - trade['entry_price']) / trade['entry_price']) * 100
        result = 'WIN' if pnl >= 0 else 'LOSS'
        exit_time = datetime.utcnow().isoformat()
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        self.db.update_trade(trade['id'], {
            'status': 'closed',
            'exit_price': price,
            'exit_time': exit_time,
            'pnl': pnl,
            'pnl_percentage': pnl_percentage,
            'result': result
        })
        logger.info(f"Closed trade {trade['coin']} PNL: {pnl}")

        # Send Telegram alert
        if reason == 'SL':
            await self.telegram.send_sl_hit(trade['coin'], price, abs(pnl_percentage), timestamp)
        elif reason == 'TP3':
            await self.telegram.send_tp_hit(trade['coin'], reason, price, pnl_percentage, timestamp)

        # Check consecutive losses
        consecutive_losses = self.db.get_consecutive_losses()
        if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            self.pause_trading()

    def pause_trading(self):
        self.paused_until = datetime.utcnow() + timedelta(hours=PAUSE_HOURS)
        logger.info(f"Trading paused until {self.paused_until}")
        # Send alert
        asyncio.create_task(self.telegram.send_trading_pause(self.paused_until.strftime('%Y-%m-%d %H:%M:%S UTC')))

    def is_paused(self):
        return self.paused_until and datetime.utcnow() < self.paused_until

    async def check_emergency_drops(self):
        for coin in COINS:
            df_1m = self.analyzer.fetch_candles(coin, '1m', limit=60)
            if df_1m is not None and len(df_1m) >= 60:
                current_price = df_1m['close'].iloc[-1]
                price_60min_ago = df_1m['close'].iloc[0]
                drop_pct = ((price_60min_ago - current_price) / price_60min_ago) * 100
                if drop_pct >= 10:
                    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                    await self.telegram.send_emergency_alert(coin, drop_pct, timestamp)

    async def send_status_report(self):
        # Calculate market condition (average or something)
        conditions = []
        for coin in COINS:
            df_4h = self.analyzer.fetch_candles(coin, '4H')
            if df_4h is not None:
                df_4h = self.analyzer.calculate_indicators(df_4h)
                conditions.append(self.analyzer.get_market_condition(df_4h))
        # Simple majority
        from collections import Counter
        if conditions:
            market_condition = Counter(conditions).most_common(1)[0][0]
        else:
            market_condition = 'TRENDING_DOWN'

        open_trades = len(self.db.get_open_trades())
        capital_used = open_trades * TRADE_SIZE_USD
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        await self.telegram.send_status_report(market_condition, self.opportunities_since_report, open_trades, capital_used, timestamp)
        self.opportunities_since_report = 0

    async def send_weekly_report(self):
        # Calculate weekly stats from database
        all_trades = self.db.get_all_trades()
        # Filter last week - only closed trades
        week_ago = datetime.utcnow() - timedelta(days=7)
        weekly_trades = [t for t in all_trades if t['exit_time'] and datetime.fromisoformat(t['exit_time']) > week_ago and t['status'] == 'closed']
        total_trades = len(weekly_trades)
        wins = len([t for t in weekly_trades if t['result'] == 'WIN'])
        losses = len([t for t in weekly_trades if t['result'] == 'LOSS'])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        pnl = sum(t['pnl'] for t in weekly_trades if t['pnl'] is not None)
        # Best/worst coin
        coin_pnl = {}
        for t in weekly_trades:
            coin_pnl[t['coin']] = coin_pnl.get(t['coin'], 0) + (t['pnl'] if t['pnl'] is not None else 0)
        best_coin = max(coin_pnl, key=coin_pnl.get) if coin_pnl else 'N/A'
        worst_coin = min(coin_pnl, key=coin_pnl.get) if coin_pnl else 'N/A'
        date_range = f"{(datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')} to {datetime.utcnow().strftime('%Y-%m-%d')}"
        await self.telegram.send_weekly_report(date_range, total_trades, wins, losses, win_rate, pnl, best_coin, worst_coin)