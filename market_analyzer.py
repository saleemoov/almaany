import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime
from config import *
from logger import logger

def api_call_with_retry(func, *args, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                logger.error(f"API failed after {max_retries} attempts: {e}")
                return None

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series, period):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

class MarketAnalyzer:
    def __init__(self):
        self.base_url = OKX_BASE_URL
        self.last_news_check = {}

    def fetch_candles(self, coin, timeframe, limit=CANDLES_COUNT):
        url = f"{self.base_url}/api/v5/market/candles"
        params = {'instId': f'{coin}-USDT', 'bar': timeframe, 'limit': limit}
        def _call():
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data['code'] != '0':
                raise Exception(f"OKX API error: {data['msg']}")
            candles = []
            for candle in data['data']:
                candles.append({
                    'timestamp': int(candle[0]),
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5])
                })
            return pd.DataFrame(candles)
        return api_call_with_retry(_call)

    def calculate_indicators(self, df):
        if df is None or df.empty:
            return None
        df = df.sort_values('timestamp')
        df['ema21'] = calculate_ema(df['close'], EMA21_PERIOD)
        df['ema50'] = calculate_ema(df['close'], EMA50_PERIOD)
        df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
        df['volume_avg'] = df['volume'].rolling(VOLUME_AVG_PERIOD).mean()
        return df

    def get_market_condition(self, df_4h):
        if df_4h is None or len(df_4h) < SR_PERIOD:
            return 'TRENDING_DOWN'
        last = df_4h.iloc[-1]
        ema21 = last['ema21']
        ema50 = last['ema50']
        support = df_4h['low'].tail(SR_PERIOD).min()
        resistance = df_4h['high'].tail(SR_PERIOD).max()
        if abs(ema21 - ema50) / ema50 < EMA_THRESHOLD:
            return 'SIDEWAYS'
        elif ema21 > ema50:
            return 'TRENDING_UP'
        else:
            return 'TRENDING_DOWN'

    def calculate_signal_score(self, df_1h, market_condition, support, coin):
        if df_1h is None or df_1h.empty:
            return 0
        last = df_1h.iloc[-1]
        ema21 = last['ema21']
        ema50 = last['ema50']
        rsi = last['rsi']
        volume = last['volume']
        volume_avg = last['volume_avg']
        current_price = last['close']
        score = 0
        # EMA aligned
        if ema21 > ema50:
            score += 25
        # RSI rules
        if market_condition == 'TRENDING_UP' and 50 <= rsi <= 65:
            score += 25
        elif market_condition == 'SIDEWAYS' and 35 <= rsi <= 50:
            score += 25
        # Volume confirmation
        volume_ratio = volume / volume_avg if volume_avg else 0
        if volume_ratio >= 1.5:
            score += 25
        # Bullish candle pattern
        if last['close'] > last['open']:
            score += 25
        # Special for sideways: entry only if price within 1.5% above support
        if market_condition == 'SIDEWAYS':
            if not (current_price <= support * (1 + SIDEWAYS_ENTRY_THRESHOLD)):
                return 0
        return score


    def get_current_price(self, coin):
        url = f"{self.base_url}/api/v5/market/ticker"
        params = {'instId': f'{coin}-USDT'}
        def _call():
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data['code'] == '0' and data['data']:
                return float(data['data'][0]['last'])
            return None
        return api_call_with_retry(_call)

    def check_emergency_drop(self, coin):
        df_1m = self.fetch_candles(coin, TIMEFRAME_1M, limit=60)
        if df_1m is None or len(df_1m) < 60:
            return False
        current_price = df_1m['close'].iloc[-1]
        price_60min_ago = df_1m['close'].iloc[0]
        drop = (price_60min_ago - current_price) / price_60min_ago
        return drop >= EMERGENCY_DROP_PCT