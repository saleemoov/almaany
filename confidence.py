# confidence.py - Confidence scoring for ELITE V9

from typing import Dict
import pandas as pd
from indicators import rsi, stoch_kd, bollinger_bands, adx, ema, atr, volume_sma, lowest


def calculate_confidence(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculates the confidence score for a given 30m candle dataframe (last row is current candle).
    Returns a dict with score breakdown and total.
    """
    score = 0
    breakdown = {}
    close = df['close']
    low = df['low']
    volume = df['volume']
    # Indicators
    rsi_val = rsi(close, 8)
    stoch_k, stoch_d = stoch_kd(df, 10, 3, 3)
    bb_upper, bb_mid, bb_lower = bollinger_bands(close, 12, 2.0)
    adx_val, di_plus, di_minus = adx(df, 14)
    atr_val = atr(df, 14)
    vol_sma = volume_sma(volume, 20)
    # True bottom
    is_bottom = (
        rsi_val < 30 and
        stoch_k < 15 and stoch_d < 15 and
        close.iloc[-1] <= bb_lower and
        low.iloc[-1] <= lowest(low, 20) * 1.01
    )
    breakdown['is_bottom'] = int(is_bottom)
    if is_bottom:
        score += 30
    # Volume
    if volume.iloc[-1] > vol_sma * 1.2:
        score += 20
        breakdown['volume'] = 1
    else:
        breakdown['volume'] = 0
    # ADX
    if adx_val >= 20 and di_plus > di_minus:
        score += 20
        breakdown['adx'] = 1
    else:
        breakdown['adx'] = 0
    # Stochastic cross
    stoch_cross = stoch_k > stoch_d and df['close'].iloc[-2] < df['close'].iloc[-1]
    if stoch_cross:
        score += 15
        breakdown['stoch_cross'] = 1
    else:
        breakdown['stoch_cross'] = 0
    # Bullish candle
    bullish = close.iloc[-1] > df['open'].iloc[-1] and (df['high'].iloc[-1] - df['low'].iloc[-1]) > atr_val * 0.5
    if bullish:
        score += 10
        breakdown['bullish'] = 1
    else:
        breakdown['bullish'] = 0
    # RSI improvement
    if rsi_val > rsi(close[:-1], 8):
        score += 5
        breakdown['rsi_up'] = 1
    else:
        breakdown['rsi_up'] = 0
    breakdown['total'] = score
    return breakdown
