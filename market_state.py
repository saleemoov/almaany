# market_state.py - Market regime detection for ELITE V9
from indicators import ema
import pandas as pd
from typing import Literal

MarketState = Literal['BULL', 'BEAR', 'SIDEWAYS']

def detect_market_state(df_4h: pd.DataFrame, df_1d: pd.DataFrame) -> MarketState:
    close_4h = df_4h['close'].iloc[-1]
    ema50_4h = ema(df_4h['close'], 50)
    close_1d = df_1d['close'].iloc[-1]
    ema200_1d = ema(df_1d['close'], 200)
    if close_4h > ema50_4h and close_1d > ema200_1d:
        return 'BULL'
    elif close_4h < ema50_4h and close_1d < ema200_1d:
        return 'BEAR'
    else:
        return 'SIDEWAYS'
