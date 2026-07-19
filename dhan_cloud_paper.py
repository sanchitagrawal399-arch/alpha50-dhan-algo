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
# 📈 PURE PANDAS ADX CALCULATION (NO TA-LIB SHORTCUTS)
# ==============================================================================
def calculate_adx(df, periods=14):
    df = df.copy()
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    # TR (True Range)
    tr1 = high - low
    tr2 = np.abs(high - close.shift(1))
    tr3 = np.abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Directional Movement (+DM and -DM)
    up_move = high.diff()
    down_move = low.diff().shift(-1) # Shift inversion for matching down movement
    down_move = -low.diff()
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    # Smoothed Wilder's values
    atr = tr.ewm(alpha=1/periods, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1/periods, adjust=False).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1/periods, adjust=False).mean() / atr)
    
    # Directional Movement Index (DX) & ADX
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/periods, adjust=False).mean()
    
    return adx

# ==============================================================================
# 📉 STRATEGY ENGINE (ORIGINAL BACKTESTED LOGIC ONLY)
# ==============================================================================
def calculate_indicators_and_signals(df):
    df = df.copy()
    
    # 1. Base Indicators
    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()
    
    # ATR Calculation
    high_low = df['High'] - df['Low']
    high_cp = np.abs(df['High'] - df['Close'].shift())
    low_cp = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1).rolling(window=14).mean()
    
    # VWAP Calculation
    df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    df["VOL20"] = df["Volume"].rolling(window=20).mean()
    
    # RSI Calculation
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # Dynamic ADX Integration (No bypass)
    df["ADX"] = calculate_adx(df, periods=14)
    
    # Intraday Time Filter
    time_filter = (df.index.time >= dt_time(9, 30)) & (df.index.time <= dt_time(15, 0))
    
    long_trend = (df["Close"] > df["VWAP"]) & (df["EMA9"] > df["EMA21"]) & (df["ADX"] >= 23)
    short_trend = (df["Close"] < df["VWAP"]) & (df["EMA9"] < df["EMA21"]) & (df["ADX"] >= 23)

    pullback_buy = long_trend & (df["Low"] <= df["EMA9"]) & (df["Close"] > df["EMA21"]) & (df["RSI"] >= 40) & (df["RSI"] <= 60)
    pullback_sell = short_trend & (df["High"] >= df["EMA9"]) & (df["Close"] < df["EMA21"]) & (df["RSI"] >= 40) & (df["RSI"] <= 60)

    pullback_buy_window = pullback_buy.rolling(window=3, min_periods=1).sum() > 0
    pullback_sell_window = pullback_sell.rolling(window=3, min_periods=1).sum() > 0

    buy = pullback_buy_window.shift(1).fillna(False) & (df["Close"] > df["EMA9"]) & (df["RSI"] > df["RSI"].shift(1)) & (df["Volume"] >= df["VOL20"]) & time_filter
    sell = pullback_sell_window.shift(1).fillna(False) & (df["Close"] < df["EMA9"]) & (df["RSI"] < df["RSI"].shift(1)) & (df["Volume"] >= df["VOL20"]) & time_filter

    df["Signal"] = ""
    df.loc[buy, "Signal"] = "BUY"
    df.loc[sell, "Signal"] = "SELL"
    
    # Original Risk-Reward Rules based on Dynamic ADX
    df["RR_Multiplier"] = np.where(df["ADX"] >= 35, 2.8, np.where(df["ADX"] >= 23, 1.8, 1.2))
    
    long_sl = pd.concat([df["Low"].shift(1), df["Low"]], axis=1).min(axis=1) - (0.10 * df["ATR"])
    short_sl = pd.concat([df["High"].shift(1), df["High"]], axis=1).max(axis=1) + (0.10 * df["ATR"])
    
    df["StopLoss"] = np.where(buy, long_sl, np.where(sell, short_sl, np.nan))
    df["Target"] = np.where(buy, df["Close"] + ((df["Close"] - df["StopLoss"]) * df["RR_Multiplier"]),
                            np.where(sell, df["Close"] - ((df["StopLoss"] - df["Close"]) * df["RR_Multiplier"]), np.nan))
    
    return df

# ==============================================================================
# 🌐 DUMMY SERVER (Render Port Bypass)
# ==============================================================================
def start_dummy_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), lambda *args: BaseHTTPRequestHandler(*args))
    print(f"✅ Web Server running on port {port}...", flush=True)
    server.serve_forever()

# ==============================================================================
# 🤖 AUTOMATED PAPER TRADING ENGINE
# ==============================================================================
def run_trading_bot():
    print("🚀 Alpha50 15-Min Paper Trading Engine Live...", flush=True)
    
    WATCHLIST = ["INFY.NS", "RELIANCE.NS", "TCS.NS"] 
    
    while True:
        now = datetime.now().time()
        
        if dt_time(9, 15) <= now <= dt_time(15, 30):
            for stock in WATCHLIST:
                try:
                    ticker = yf.Ticker(stock)
                    df = ticker.history(period="5d", interval="15m")
                    
                    if df.empty:
                        continue
                        
                    processed_df = calculate_indicators_and_signals(df)
                    last_row = processed_df.iloc[-1]
                    
                    if last_row["Signal"] in ["BUY", "SELL"]:
                        print(f"🔥 15-MIN PAPER SIGNAL: {stock} -> {last_row['Signal']}", flush=True)
                        log_trade(
                            stock=stock.replace(".NS", ""),
                            t_type=last_row["Signal"],
                            e_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            e_price=float(last_row["Close"]),
                            sl=float(last_row["StopLoss"]) if not pd.isna(last_row["StopLoss"]) else 0,
                            target=float(last_row["Target"]) if not pd.isna(last_row["Target"]) else 0,
                            qty=10, 
                            status="PAPER_LIVE"
                        )
                except Exception as e:
                    print(f"❌ Error tracking {stock}: {str(e)}", flush=True)
                    
        else:
            print(f"💤 Market Closed ({datetime.now().strftime('%H:%M:%S')}). Sleeping...", flush=True)
            time.sleep(900)
            continue
            
        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    run_trading_bot()
