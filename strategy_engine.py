import pandas as pd
import numpy as np

# ==========================================
# 1. INDICATORS ENGINE
# ==========================================
def adx(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_val = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr_val)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr_val)
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di)) * 100
    adx_val = dx.rolling(period).mean()
    result = pd.DataFrame()
    result["ADX"] = adx_val
    result["PLUS_DI"] = plus_di
    result["MINUS_DI"] = minus_di
    return result

def atr(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def ema(data: pd.Series, period: int):
    return data.ewm(span=period, adjust=False).mean()

def rsi(data: pd.Series, period: int = 14):
    delta = data.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def volume_ma(volume, period=20):
    return volume.rolling(period).mean()

def vwap(df):
    df = df.copy()
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    df["VWAP"] = (tp * df["Volume"]).cumsum() / df["Volume"].cumsum()
    return df["VWAP"]

# ==========================================
# 2. TRADE FILTERS
# ==========================================
def apply_trade_filters(df):
    df = df.copy()
    if df.empty or "Signal" not in df.columns:
        return df

    df["Risk"] = abs(df["Entry"] - df["StopLoss"])
    
    # Wider Risk Range Filter: 0.6*ATR to 2.5*ATR to allow breathable SL
    valid_risk = (df["Risk"] >= (0.60 * df["ATR"])) & (df["Risk"] <= (2.50 * df["ATR"]))
    adx_rising = df["ADX"] > df["ADX"].shift(1)
    time_runway = df.index.time <= pd.to_datetime("13:45").time()

    master_filter = valid_risk & adx_rising & time_runway

    df.loc[~master_filter, "Signal"] = ""
    df.loc[~master_filter, "Entry"] = None
    df.loc[~master_filter, "StopLoss"] = None
    df.loc[~master_filter, "Target"] = None
    
    df = df.drop(columns=["Risk"], errors="ignore")
    return df

# ==========================================
# 3. STRATEGY SIGNAL GENERATOR
# ==========================================
def generate_signals(df):
    df = df.copy()
    df["EMA9"], df["EMA21"] = ema(df["Close"], 9), ema(df["Close"], 21)
    df["ATR"], df["VWAP"], df["VOL20"], df["RSI"] = atr(df, 14), vwap(df), volume_ma(df["Volume"], 20), rsi(df["Close"], 14)
    
    adx_data = adx(df, 14)
    df["ADX"], df["PLUS_DI"], df["MINUS_DI"] = adx_data["ADX"], adx_data["PLUS_DI"], adx_data["MINUS_DI"]

    time_filter = (df.index.time >= pd.to_datetime("10:00").time()) & (df.index.time <= pd.to_datetime("14:30").time())
    long_trend = (df["Close"] > df["VWAP"]) & (df["EMA9"] > df["EMA21"]) & (df["ADX"] >= 22) & (df["PLUS_DI"] > df["MINUS_DI"])
    short_trend = (df["Close"] < df["VWAP"]) & (df["EMA9"] < df["EMA21"]) & (df["ADX"] >= 22) & (df["PLUS_DI"] < df["MINUS_DI"])

    pullback_buy = long_trend & (df["Low"] <= df["EMA9"]) & (df["Close"] > df["EMA21"]) & (df["RSI"] >= 40) & (df["RSI"] <= 60)
    pullback_sell = short_trend & (df["High"] >= df["EMA9"]) & (df["Close"] < df["EMA21"]) & (df["RSI"] >= 40) & (df["RSI"] <= 60)
    
    pullback_buy_window = pullback_buy.rolling(window=3, min_periods=1).sum() > 0
    pullback_sell_window = pullback_sell.rolling(window=3, min_periods=1).sum() > 0

    buy = pullback_buy_window.shift(1).fillna(False) & (df["Close"] > df["EMA9"]) & (df["RSI"] > df["RSI"].shift(1)) & (df["Volume"] >= df["VOL20"]) & time_filter
    sell = pullback_sell_window.shift(1).fillna(False) & (df["Close"] < df["EMA9"]) & (df["RSI"] < df["RSI"].shift(1)) & (df["Volume"] >= df["VOL20"]) & time_filter

    df["Signal"] = ""
    df.loc[buy, "Signal"], df.loc[sell, "Signal"] = "BUY", "SELL"
    df["Entry"] = df["Open"].shift(-1)
    df["RR_Multiplier"] = np.where(df["ADX"] >= 35, 2.5, np.where(df["ADX"] >= 23, 2.0, 1.5))

    # WIDER SL: Swing Low/High +/- 0.8 * ATR (realistic breathable range)
    long_sl = pd.concat([df["Low"].shift(1), df["Low"]], axis=1).min(axis=1) - (0.80 * df["ATR"])
    short_sl = pd.concat([df["High"].shift(1), df["High"]], axis=1).max(axis=1) + (0.80 * df["ATR"])

    df["StopLoss"], df["Target"] = np.nan, np.nan
    if buy.any():
        df.loc[buy, "StopLoss"] = long_sl[buy].values
        df.loc[buy, "Target"] = (df.loc[buy, "Entry"] + ((df.loc[buy, "Entry"] - df.loc[buy, "StopLoss"]) * df.loc[buy, "RR_Multiplier"])).values
    if sell.any():
        df.loc[sell, "StopLoss"] = short_sl[sell].values
        df.loc[sell, "Target"] = (df.loc[sell, "Entry"] - ((df.loc[sell, "StopLoss"] - df.loc[sell, "Entry"]) * df.loc[sell, "RR_Multiplier"])).values

    return apply_trade_filters(df)
