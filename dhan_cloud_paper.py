import os
import threading
import time
import gspread
import pandas as pd
import numpy as np
import yfinance as yf
from http.server import BaseHTTPRequestHandler, HTTPServer
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, time as dt_time

# ==============================================================================
# 🛠️ SETUP: GOOGLE SHEETS CONNECTION
# ==============================================================================
creds = ServiceAccountCredentials.from_json_keyfile_name(
    'service_account.json', 
    ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ.get("MY_SECRET_SHEET_ID")).worksheet("Trades")

def log_trade(stock, t_type, e_time, e_price, sl, target, qty, status):
    row = [stock, t_type, e_time, "", e_price, "", sl, target, qty, status]
    sheet.append_row(row)

# ==============================================================================
# 📈 PURE PANDAS MATH ENGINE (EXACT MATCH FOR YOUR CODE)
# ==============================================================================
def calculate_adx_components(df, periods=14):
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    tr1 = high - low
    tr2 = np.abs(high - close.shift(1))
    tr3 = np.abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    up_move = high.diff()
    down_move = -low.diff()
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    atr_smooth = tr.ewm(alpha=1/periods, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1/periods, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1/periods, adjust=False).mean() / atr_smooth)
    
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx_series = dx.ewm(alpha=1/periods, adjust=False).mean()
    
    return adx_series, plus_di, minus_di

def apply_trade_filters(df):
    """
    Apply advanced structural and momentum risk filters to maximize target probability.
    Returns:
        DataFrame
    """
    df = df.copy()

    # Ensure we don't calculate on empty frames
    if df.empty or "Signal" not in df.columns:
        return df

    # ==========================================
    # 1. Structural Risk Distance Matrix
    # ==========================================
    df["Risk"] = abs(df["Entry"] - df["StopLoss"])

    # Base structural compliance: Risk must be in standard distribution bounds
    valid_risk = (
        (df["Risk"] >= (0.30 * df["ATR"])) &
        (df["Risk"] <= (1.50 * df["ATR"]))
    )

    # ==========================================
    # 2. ADX Directional Momentum Filter
    # ==========================================
    # Eliminates entries when the trend strength is flattening out or decaying
    adx_rising = df["ADX"] > df["ADX"].shift(1)

    # ==========================================
    # 3. Time Runway Matrix (Execution Window Cap)
    # ==========================================
    # Blocks entries after 13:45 (1:45 PM IST) because the remaining session length 
    # is mathematically insufficient to hit a full 2.0 RR extension before square-off.
    time_runway = df.index.time <= pd.to_datetime("13:45").time()

    # ==========================================
    # Composite Master Filter Alignment
    # ==========================================
    # A signal is only valid if all structural, momentum, and time components pass
    master_filter = valid_risk & adx_rising & time_runway

    # ==========================================
    # Clean and Purge Non-Compliant Signals
    # ==========================================
    df.loc[~master_filter, "Signal"] = ""
    df.loc[~master_filter, "Entry"] = None
    df.loc[~master_filter, "StopLoss"] = None
    df.loc[~master_filter, "Target"] = None

    # Drop the temporary helper column to keep the main DataFrame clean
    df = df.drop(columns=["Risk"])

    return df

def generate_signals(df):
    df = df.copy()

    # =====================================================
    # Indicators
    # =====================================================
    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()
    
    high_low = df['High'] - df['Low']
    high_cp = np.abs(df['High'] - df['Close'].shift())
    low_cp = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1).rolling(window=14).mean()
    
    df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    df["VOL20"] = df["Volume"].rolling(window=20).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df["ADX"], df["PLUS_DI"], df["MINUS_DI"] = calculate_adx_components(df, 14)

    # =====================================================
    # Time Filter (10:00 to 14:30)
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
    # Signal Assignment & Target/SL Logic
    # =====================================================
    df["Signal"] = ""
    df.loc[buy, "Signal"] = "BUY"
    df.loc[sell, "Signal"] = "SELL"

    df["Entry"] = df["Open"].shift(-1)

    df["RR_Multiplier"] = np.where(
        df["ADX"] >= 35, 2.8,
        np.where(df["ADX"] >= 23, 1.8, 1.2)
    )

    long_sl_series = pd.concat([df["Low"].shift(1), df["Low"]], axis=1).min(axis=1) - (0.10 * df["ATR"])
    short_sl_series = pd.concat([df["High"].shift(1), df["High"]], axis=1).max(axis=1) + (0.10 * df["ATR"])

    df["StopLoss"] = np.nan
    df["Target"] = np.nan

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
    # Apply Advanced Trade Filters (Risk, ADX Momentum, Time)
    # =====================================================
    df = apply_trade_filters(df)

    return df

# ==============================================================================
# 🌐 DUMMY SERVER & AUTOMATION CORE
# ==============================================================================
def start_dummy_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), lambda *args: BaseHTTPRequestHandler(*args))
    print(f"✅ Web Server running on port {port}...", flush=True)
    server.serve_forever()

def run_trading_bot():
    print("🚀 Alpha50 Strict Backtested Engine Live...", flush=True)
    
    # YOUR EXACT STOCK LIST
    stocks = [
        "NESTLEIND", "DRREDDY", "ICICIBANK", "GRASIM", "CIPLA", 
        "BPCL", "POWERGRID", "ADANIPORTS", "COALINDIA", 
        "SUNPHARMA", "HEROMOTOCO", "AXISBANK", "BHARTIARTL", 
        "LT", "M_and_M", "RELIANCE", "SBIN", "NTPC"
    ]
    
    while True:
        now = datetime.now().time()
        
        # Live Market Scanner loop
        if dt_time(9, 15) <= now <= dt_time(15, 30):
            for stock in stocks:
                try:
                    # Handle M_and_M specific formatting for Yahoo Finance
                    yf_symbol = stock.replace("M_and_M", "M&M") + ".NS"
                    
                    ticker = yf.Ticker(yf_symbol)
                    df = ticker.history(period="5d", interval="15m")
                    
                    if df.empty or len(df) < 30:
                        continue
                        
                    processed_df = generate_signals(df)
                    
                    if len(processed_df) >= 2:
                        signal_row = processed_df.iloc[-2] # Checking previous closed candle for signals
                        live_candle = processed_df.iloc[-1] # This is the current open candle where execution happens
                        
                        if signal_row["Signal"] in ["BUY", "SELL"]:
                            print(f"🔥 STRICT SIGNAL MATCHED: {stock} -> {signal_row['Signal']}", flush=True)
                            log_trade(
                                stock=stock, # Original name in sheet
                                t_type=signal_row["Signal"],
                                e_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                e_price=float(live_candle["Open"]), # Current candle opening price (actual entry)
                                sl=float(signal_row["StopLoss"]) if not pd.isna(signal_row["StopLoss"]) else 0,
                                target=float(signal_row["Target"]) if not pd.isna(signal_row["Target"]) else 0,
                                qty=10, 
                                status="PAPER_LIVE"
                            )
                except Exception as e:
                    print(f"❌ Error scanning {stock}: {str(e)}", flush=True)
                    
            time.sleep(60)
        else:
            print(f"💤 Market Closed ({datetime.now().strftime('%H:%M:%S')}). Sleeping...", flush=True)
            time.sleep(900)

if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    run_trading_bot()
