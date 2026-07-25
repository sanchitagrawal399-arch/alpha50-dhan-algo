import pandas as pd
import numpy as np

from src.indicators.ema import ema
from src.indicators.atr import atr
from src.indicators.volume import volume_ma
from src.indicators.vwap import vwap
from src.indicators.adx import adx
from src.indicators.rsi import rsi
from src.risk.filters import apply_trade_filters


def generate_signals(df):
    df = df.copy()

    # =====================================================
    # Indicators
    # =====================================================
    df["EMA9"] = ema(df["Close"], 9)
    df["EMA21"] = ema(df["Close"], 21)
    df["ATR"] = atr(df, 14)
    df["VWAP"] = vwap(df)
    df["VOL20"] = volume_ma(df["Volume"], 20)
    df["RSI"] = rsi(df["Close"], 14)

    adx_data = adx(df, 14)
    df["ADX"] = adx_data["ADX"]
    df["PLUS_DI"] = adx_data["PLUS_DI"]
    df["MINUS_DI"] = adx_data["MINUS_DI"]

    # =====================================================
    # Time Filter (Tightened to reduce morning fakeouts)
    # =====================================================
    time_filter = (
        (df.index.time >= pd.to_datetime("10:00").time()) &
        (df.index.time <= pd.to_datetime("14:30").time())
    )

    # =====================================================
    # Trend Filter
    # =====================================================
    long_trend = (
        (df["Close"] > df["VWAP"]) &
        (df["EMA9"] > df["EMA21"]) &
        (df["ADX"] >= 23) &
        (df["PLUS_DI"] > df["MINUS_DI"])
    )

    short_trend = (
        (df["Close"] < df["VWAP"]) &
        (df["EMA9"] < df["EMA21"]) &
        (df["ADX"] >= 23) &
        (df["PLUS_DI"] < df["MINUS_DI"])
    )

    # =====================================================
    # Pullback Candle
    # =====================================================
    pullback_buy = (
        long_trend &
        (df["Low"] <= df["EMA9"]) &
        (df["Close"] > df["EMA21"]) &
        (df["RSI"] >= 40) &
        (df["RSI"] <= 60)
    )

    pullback_sell = (
        short_trend &
        (df["High"] >= df["EMA9"]) &
        (df["Close"] < df["EMA21"]) &
        (df["RSI"] >= 40) &
        (df["RSI"] <= 60)
    )

    # Rolling window lookback (Allows up to 3 candles of pullback consolidation)
    pullback_buy_window = pullback_buy.rolling(window=3, min_periods=1).sum() > 0
    pullback_sell_window = pullback_sell.rolling(window=3, min_periods=1).sum() > 0

    # =====================================================
    # Signal Candle
    # =====================================================
    buy = (
        pullback_buy_window.shift(1).fillna(False) &
        (df["Close"] > df["EMA9"]) &
        (df["RSI"] > df["RSI"].shift(1)) &
        (df["Volume"] >= df["VOL20"]) &
        time_filter
    )

    sell = (
        pullback_sell_window.shift(1).fillna(False) &
        (df["Close"] < df["EMA9"]) &
        (df["RSI"] < df["RSI"].shift(1)) &
        (df["Volume"] >= df["VOL20"]) &
        time_filter
    )

    # =====================================================
    # Signal Assignment
    # =====================================================
    df["Signal"] = ""
    df.loc[buy, "Signal"] = "BUY"
    df.loc[sell, "Signal"] = "SELL"

    # Entry is execution on next candle's opening price
    df["Entry"] = df["Open"].shift(-1)

    # =====================================================
    # ⚡ Dynamic RR Scaling Factor (Mathematical Engine)
    # =====================================================
    # If trend is incredibly strong (ADX >= 35), let winners run up to 2.8x RR.
    # If trend is moderate (ADX >= 23), use standard 1.8x RR.
    # If trend is weak (ADX < 23), take quick profit at 1.2x RR to avoid reversal.
    df["RR_Multiplier"] = np.where(
        df["ADX"] >= 35, 2.8,
        np.where(df["ADX"] >= 23, 1.8, 1.2)
    )

    # =====================================================
    # Stop Loss & Target Logic (Dynamic Target Profile)
    # =====================================================
    long_sl_series = pd.concat([df["Low"].shift(1), df["Low"]], axis=1).min(axis=1) - (0.10 * df["ATR"])
    short_sl_series = pd.concat([df["High"].shift(1), df["High"]], axis=1).max(axis=1) + (0.10 * df["ATR"])

    df["StopLoss"] = np.nan
    df["Target"] = np.nan

    # Vectorized precise assignment using the dynamic ADX multiplier
    if buy.any():
        df.loc[buy, "StopLoss"] = long_sl_series[buy].values
        df.loc[buy, "Target"] = (
            df.loc[buy, "Entry"] + 
            ((df.loc[buy, "Entry"] - df.loc[buy, "StopLoss"]) * df.loc[buy, "RR_Multiplier"])
        ).values

    if sell.any():
        df.loc[sell, "StopLoss"] = short_sl_series[sell].values
        df.loc[sell, "Target"] = (
            df.loc[sell, "Entry"] - 
            ((df.loc[sell, "StopLoss"] - df.loc[sell, "Entry"]) * df.loc[sell, "RR_Multiplier"])
        ).values

    # =====================================================
    # Apply Operational Risk Filters
    # =====================================================
    df = apply_trade_filters(df)

    return df