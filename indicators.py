# indicators.py - All indicator calculations for ELITE V9
import pandas as pd
import numpy as np
from typing import Tuple

def rsi(series: pd.Series, length: int = 8) -> float:
    delta = series.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=length - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=length - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    return float(rsi_series.iloc[-1])

def stoch_kd(df: pd.DataFrame, length: int = 10, smooth_k: int = 3, smooth_d: int = 3) -> Tuple[float, float]:
    low_min = df['low'].rolling(window=length).min()
    high_max = df['high'].rolling(window=length).max()
    k = 100 * (df['close'] - low_min) / (high_max - low_min)
    k = k.rolling(window=smooth_k).mean()
    d = k.rolling(window=smooth_d).mean()
    return float(k.iloc[-1]), float(d.iloc[-1])

def bollinger_bands(series: pd.Series, length: int = 12, multiplier: float = 2.0) -> Tuple[float, float, float]:
    sma = series.rolling(window=length).mean()
    std = series.rolling(window=length).std()
    upper = sma + multiplier * std
    lower = sma - multiplier * std
    return float(upper.iloc[-1]), float(sma.iloc[-1]), float(lower.iloc[-1])

def adx(df: pd.DataFrame, length: int = 14) -> Tuple[float, float, float]:
    high = df['high']
    low = df['low']
    close = df['close']
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=length).mean()
    plus_di = 100 * plus_dm.rolling(window=length).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.rolling(window=length).mean() / atr.replace(0, np.nan)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx_val = dx.rolling(window=length).mean()
    return float(adx_val.iloc[-1]), float(plus_di.iloc[-1]), float(minus_di.iloc[-1])

def atr(df: pd.DataFrame, length: int = 14) -> float:
    high = df['high']
    low = df['low']
    close = df['close']
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return float(tr.rolling(window=length).mean().iloc[-1])

def volume_sma(series: pd.Series, length: int = 20) -> float:
    return float(series.rolling(window=length).mean().iloc[-1])

def ema(series: pd.Series, length: int) -> float:
    return float(series.ewm(span=length, adjust=False).mean().iloc[-1])

def lowest(series: pd.Series, length: int) -> float:
    return float(series.rolling(window=length).min().iloc[-1])

def highest(series: pd.Series, length: int) -> float:
    return float(series.rolling(window=length).max().iloc[-1])
