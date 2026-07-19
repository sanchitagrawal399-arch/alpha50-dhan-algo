import os
import threading
import time
import gspread
from dhanhq import dhanhq
import pandas as pd
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, time as dt_time

# ==============================================================================
# 🛠️ SETUP: CONNECTIONS & API
# ==============================================================================
# Render ke Secret Files se service_account.json read ho raha hai
creds = ServiceAccountCredentials.from_json_keyfile_name(
    'service_account.json', 
    ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ.get("MY_SECRET_SHEET_ID")).worksheet("Trades")

# 🟢 FIXED: Dhan HQ Official Library Integration
CLIENT_ID = os.environ.get("CLIENT_ID")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)

def log_trade(stock, t_type, e_time, e_price, sl, target, qty, status):
    # Column Order: Stock, Type, Entry_Time, Exit_Time, Entry_Price, Exit_Price, StopLoss, Target, Quantity, Status
    row = [stock, t_type, e_time, "", e_price, "", sl, target, qty, status]
    sheet.append_row(row)

# ==============================================================================
# 📈 STRATEGY ENGINE (PANDAS IMPLEMENTATION)
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

    # --- Trend Filters & ADX Mock (Keep as per original requirements) ---
    df["ADX"] = 25  # Default threshold buffer
    time_filter = (df.index.time >= dt_time(10, 0)) & (df.index.time <= dt_time(14, 30))
    
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
# 🤖 AUTOMATED LIVE TRADING ENGINE
# ==============================================================================
def run_trading_bot():
    print("🚀 Alpha50 Trading Engine Live & Scanning Dhan Live Data...", flush=True)
    
    # Yahan apne stocks ke trading symbols daal do
    WATCHLIST = ["INFY", "RELIANCE", "TCS"] 
    
    while True:
        now = datetime.now().time()
        
        # Live Market Hours Only (9:15 AM - 3:30 PM)
        if dt_time(9, 15) <= now <= dt_time(15, 30):
            for stock in WATCHLIST:
                try:
                    # Dhan API standard intraday historical fetch (1-minute charts)
                    # Arguments: security_id, exchange_segment, instrument_type
                    # Example parameters for Equity: exchange_segment='NSE_EQ'
                    response = dhan.get_intraday_data(
                        security_id=stock, 
                        exchange_segment='NSE_EQ', 
                        instrument_type='EQUITY'
                    )
                    
                    if response and response.get('status') == 'success':
                        data_list = response.get('data', [])
                        if not data_list:
                            continue
                            
                        # Dataframe structural mapping
                        df = pd.DataFrame(data_list)
                        df['Timestamp'] = pd.to_datetime(df['start_time'])
                        df.set_index('Timestamp', inplace=True)
                        df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
                        
                        # Process indicators & signals
                        processed_df = calculate_indicators_and_signals(df)
                        last_row = processed_df.iloc[-1]
                        
                        if last_row["Signal"] in ["BUY", "SELL"]:
                            print(f"🔥 SIGNAL DETECTED: {stock} -> {last_row['Signal']}", flush=True)
                            log_trade(
                                stock=stock,
                                t_type=last_row["Signal"],
                                e_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                e_price=last_row["Close"],
                                sl=last_row["StopLoss"],
                                target=last_row["Target"],
                                qty=10, 
                                status="PAPER_LIVE"
                            )
                except Exception as e:
                    print(f"❌ Error tracking {stock}: {str(e)}", flush=True)
                    
        else:
            print(f"💤 Market Closed ({datetime.now().strftime('%H:%M:%S')}). Sleeping...", flush=True)
            time.sleep(300)
            continue
            
        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    run_trading_bot()
