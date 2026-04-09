import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config import (
    OKX_BASE_URL, COINS, TIMEFRAME_4H, TIMEFRAME_1H, TIMEFRAME_1M, CANDLES_COUNT,
    EMA21_PERIOD, EMA50_PERIOD, RSI_PERIOD, VOLUME_AVG_PERIOD, SR_PERIOD,
    EMA_THRESHOLD, NEWS_CHECK_HOURS, CRYPTOPANIC_API_TOKEN
)
from logger import logger

def calculate_ema(data, period):
    return data.ewm(span=period, adjust=False).mean()

def calculate_rsi(data, period):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

class MarketAnalyzer:
    def __init__(self):
        self.base_url = OKX_BASE_URL

    def fetch_candles(self, coin, timeframe, limit=CANDLES_COUNT):
        """Fetch candlestick data from OKX"""
        url = f"{self.base_url}/api/v5/market/candles"
        params = {
            'instId': f'{coin}-USDT',
            'bar': timeframe,
            'limit': limit
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data['code'] != '0':
                logger.error(f"OKX API error: {data['msg']}")
                return None
            # OKX candles: [timestamp, open, high, low, close, volume]
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
        except Exception as e:
            logger.error(f"Error fetching candles for {coin}: {e}")
            return None

    def calculate_indicators(self, df):
        """Calculate EMA, RSI, etc."""
        if df is None or df.empty:
            return None
        df = df.sort_values('timestamp')
        df['ema21'] = calculate_ema(df['close'], EMA21_PERIOD)
        df['ema50'] = calculate_ema(df['close'], EMA50_PERIOD)
        df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
        df['volume_avg'] = df['volume'].rolling(VOLUME_AVG_PERIOD).mean()
        return df

    def get_market_condition(self, df_4h):
        """Determine market condition"""
        if df_4h is None or len(df_4h) < SR_PERIOD:
            return 'TRENDING_DOWN'  # default if not enough data
        last = df_4h.iloc[-1]
        ema21 = last['ema21']
        ema50 = last['ema50']
        current_close = last['close']
        support = df_4h['low'].tail(SR_PERIOD).min()
        resistance = df_4h['high'].tail(SR_PERIOD).max()

        # Check SIDEWAYS first
        if abs(ema21 - ema50) / ema50 < EMA_THRESHOLD and support <= current_close <= resistance:
            return 'SIDEWAYS'
        # Then UP or DOWN based on EMA
        elif ema21 > ema50:
            return 'TRENDING_UP'
        else:
            return 'TRENDING_DOWN'

    def calculate_signal_score(self, df_1h, market_condition, support, coin):
        """Calculate signal score"""
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

        # RSI in range
        if 40 <= rsi <= 60:
            score += 25
        elif market_condition == 'SIDEWAYS' and rsi < 45:
            score += 25  # special for sideways

        # Volume strong
        if volume > volume_avg:
            score += 25

        # No bad news
        if self.check_negative_news(coin):
            score += 25

        # Special for sideways
        if market_condition == 'SIDEWAYS':
            if not (current_price <= support * (1 + 0.015)):
                score = 0  # not within 1.5% above support

        return score

    def check_negative_news(self, coin):
        """Check for negative news using CoinGecko - Free, no token needed"""
        import time
        time.sleep(5)  # Delay to avoid rate limits
        coin_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
            'XRP': 'ripple', 'BNB': 'binancecoin', 'ADA': 'cardano',
            'AVAX': 'avalanche-2', 'DOT': 'polkadot', 'ATOM': 'cosmos',
            'DOGE': 'dogecoin'
        }
        coin_id = coin_map.get(coin)
        if not coin_id:
            return True

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        params = {'localization': 'false', 'sparkline': 'false'}
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            change_24h = data['market_data']['price_change_percentage_24h']
            sentiment = data.get('sentiment_votes_down_percentage', 0)
            if change_24h < -5 or sentiment > 60:
                return False  # negative signals
            return True  # all good
        except Exception as e:
            logger.error(f"Error checking news for {coin}: {e}")
            return True  # if API fails

    def check_emergency_drop(self, coin):
        """Check if coin dropped 10% in last 60 min"""
        df_1m = self.fetch_candles(coin, TIMEFRAME_1M, limit=60)
        if df_1m is None or len(df_1m) < 60:
            return False
        current_price = df_1m['close'].iloc[-1]
        price_60min_ago = df_1m['close'].iloc[0]
        drop = (price_60min_ago - current_price) / price_60min_ago
        return drop >= 0.10

    def get_current_price(self, coin):
        """Get current price"""
        url = f"{self.base_url}/api/v5/market/ticker"
        params = {'instId': f'{coin}-USDT'}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data['code'] == '0' and data['data']:
                return float(data['data'][0]['last'])
        except Exception as e:
            logger.error(f"Error getting current price for {coin}: {e}")
        return None