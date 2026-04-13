import time
import ccxt
import pandas as pd
import numpy as np
from logger import get_logger
from config import (
    OKX_API_KEY, OKX_SECRET, OKX_PASSWORD,
    TREND_TIMEFRAME, ENTRY_TIMEFRAME,
    RSI_UP_MIN, RSI_UP_MAX, RSI_SIDEWAYS_MIN, RSI_SIDEWAYS_MAX,
    ADX_STRONG, ADX_WEAK,
    MAX_VOLUME_SPIKE,
    SR_PERIOD,
    SIDEWAYS_ENTRY_THRESHOLD,
    EMERGENCY_DROP_PCT,
)

log = get_logger("market_analyzer")

MAX_RETRIES = 3
RETRY_WAIT = 5


def _get_exchange() -> ccxt.okx:
    return ccxt.okx({
        "apiKey": OKX_API_KEY,
        "secret": OKX_SECRET,
        "password": OKX_PASSWORD,
        "sandbox": True,
        "enableRateLimit": True,
        "headers": {"x-simulated-trading": "1"},
    })


def _fetch_ohlcv_with_retry(exchange: ccxt.okx, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not raw:
                raise ValueError(f"Empty OHLCV response for {symbol}")
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            return df
        except Exception as e:
            log.warning(f"Attempt {attempt}/{MAX_RETRIES} failed for {symbol} {timeframe}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
    log.error(f"All retries exhausted for {symbol} {timeframe}. Skipping.")
    return pd.DataFrame()


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    return float(rsi_series.iloc[-1])


def _adx(df: pd.DataFrame, period: int = 14) -> tuple:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(com=period - 1, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(com=period - 1, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(com=period - 1, adjust=False).mean() / atr.replace(0, np.nan)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx_val = dx.ewm(com=period - 1, adjust=False).mean()

    return float(adx_val.iloc[-1]), float(plus_di.iloc[-1]), float(minus_di.iloc[-1])


def get_market_condition(coin: str) -> dict:
    exchange = _get_exchange()
    symbol = f"{coin}/USDT"
    df = _fetch_ohlcv_with_retry(exchange, symbol, TREND_TIMEFRAME, 50)

    if df.empty:
        return {"condition": "TRENDING_DOWN", "support": None, "resistance": None}

    close = df["close"]
    ema21 = float(_ema(close, 21).iloc[-1])
    ema50 = float(_ema(close, 50).iloc[-1])

    support = float(df["low"].iloc[-SR_PERIOD:].min())
    resistance = float(df["high"].iloc[-SR_PERIOD:].max())

    diff_ratio = abs(ema21 - ema50) / ema50

    if diff_ratio < 0.005:
        condition = "SIDEWAYS"
    elif ema21 > ema50:
        condition = "TRENDING_UP"
    else:
        condition = "TRENDING_DOWN"

    return {
        "condition": condition,
        "support": support,
        "resistance": resistance,
        "ema21_2h": ema21,
        "ema50_2h": ema50,
    }


def calculate_signal(coin: str, condition: str, support: float) -> dict:
    exchange = _get_exchange()
    symbol = f"{coin}/USDT"
    df = _fetch_ohlcv_with_retry(exchange, symbol, ENTRY_TIMEFRAME, 60)

    if df.empty:
        return {"score": 0, "reasons": ["API error"]}

    close = df["close"]
    ema21 = float(_ema(close, 21).iloc[-1])
    ema50 = float(_ema(close, 50).iloc[-1])
    rsi_val = _rsi(close)
    adx_val, plus_di, minus_di = _adx(df)

    last_candle = df.iloc[-1]
    current_price = float(last_candle["close"])
    current_volume = float(last_candle["volume"])
    avg_volume = float(df["volume"].iloc[-20:].mean())

    score = 0
    reasons = []

    # SIDEWAYS: price must be within 1.5% above support
    if condition == "SIDEWAYS" and support is not None:
        if current_price > support * (1 + SIDEWAYS_ENTRY_THRESHOLD):
            return {"score": 0, "reasons": ["Price not near support in SIDEWAYS"], "current_price": current_price}

    # EMA aligned (20 pts)
    if ema21 > ema50:
        score += 20
        reasons.append("EMA21>EMA50 ✅")
    else:
        reasons.append("EMA21<EMA50 ❌")

    # RSI (20 pts)
    if condition == "TRENDING_UP" and RSI_UP_MIN <= rsi_val <= RSI_UP_MAX:
        score += 20
        reasons.append(f"RSI {rsi_val:.1f} in [{RSI_UP_MIN}-{RSI_UP_MAX}] ✅")
    elif condition == "SIDEWAYS" and RSI_SIDEWAYS_MIN <= rsi_val <= RSI_SIDEWAYS_MAX:
        score += 20
        reasons.append(f"RSI {rsi_val:.1f} in [{RSI_SIDEWAYS_MIN}-{RSI_SIDEWAYS_MAX}] ✅")
    else:
        reasons.append(f"RSI {rsi_val:.1f} out of range ❌")

    # Volume (20 pts)
    if current_volume > avg_volume * MAX_VOLUME_SPIKE:
        reasons.append(f"Volume spike {current_volume/avg_volume:.1f}x — pump risk ❌")
    elif current_volume > avg_volume:
        score += 20
        reasons.append(f"Volume normal {current_volume/avg_volume:.1f}x ✅")
    else:
        reasons.append(f"Volume low {current_volume/avg_volume:.1f}x ❌")

    # ADX (20 pts)
    if adx_val >= ADX_STRONG and plus_di > minus_di:
        score += 20
        reasons.append(f"ADX {adx_val:.1f}≥{ADX_STRONG}, DI+>DI- ✅")
    elif ADX_WEAK <= adx_val < ADX_STRONG and plus_di > minus_di:
        score += 10
        reasons.append(f"ADX {adx_val:.1f} moderate ⚠️")
    else:
        reasons.append(f"ADX {adx_val:.1f} weak ❌")

    # Bullish candle (20 pts)
    if float(last_candle["close"]) > float(last_candle["open"]):
        score += 20
        reasons.append("Bullish candle ✅")
    else:
        reasons.append("Bearish candle ❌")

    return {
        "score": score,
        "reasons": reasons,
        "current_price": current_price,
        "rsi": round(rsi_val, 2),
        "adx": round(adx_val, 2),
        "plus_di": round(plus_di, 2),
        "minus_di": round(minus_di, 2),
        "ema21": round(ema21, 6),
        "ema50": round(ema50, 6),
        "volume_ratio": round(current_volume / avg_volume, 2) if avg_volume else 0,
    }


def check_emergency_drop(coin: str) -> float | None:
    exchange = _get_exchange()
    symbol = f"{coin}/USDT"
    df = _fetch_ohlcv_with_retry(exchange, symbol, "1m", 61)

    if df.empty or len(df) < 2:
        return None

    price_60min_ago = float(df.iloc[-61]["close"]) if len(df) >= 61 else float(df.iloc[0]["close"])
    current_price = float(df.iloc[-1]["close"])

    if price_60min_ago == 0:
        return None

    drop = (price_60min_ago - current_price) / price_60min_ago
    if drop >= EMERGENCY_DROP_PCT:
        return round(drop * 100, 2)
    return None


def get_current_price(coin: str) -> float | None:
    exchange = _get_exchange()
    symbol = f"{coin}/USDT"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ticker = exchange.fetch_ticker(symbol)
            return float(ticker["last"])
        except Exception as e:
            log.warning(f"Price fetch attempt {attempt} failed for {coin}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
    log.error(f"Could not fetch price for {coin}")
    return None
