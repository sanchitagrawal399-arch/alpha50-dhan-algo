import os, threading, time, gspread, dhanhq
import pandas as pd
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, time as dt_time

# ==============================================================================
# 🛠️ SETUP: CONNECTIONS & API
# ==============================================================================
creds = ServiceAccountCredentials.from_json_keyfile_name(
    'service_account.json', 
    ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ.get("MY_SECRET_SHEET_ID")).worksheet("Trades")

# Dhan API init (Sheet se data reading logic ya environment variables se)
# Yahan hum assume kar rahe hain tumne variables sheet se read kiye hain ya env me hain
dhan = dhanhq.DhanApi(os.environ.get("CLIENT_ID"), os.environ.get("ACCESS_TOKEN"))

def log_trade(stock, t_type, e_time, e_price, sl, target, qty, status):
    # Column Order: Stock, Type, Entry_Time, Exit_Time, Entry_Price, Exit_Price, StopLoss, Target, Quantity, Status
    row = [stock, t_type, e_time, "", e_price, "", sl, target, qty, status]
    sheet.append_row(row)

# ==============================================================================
# 📈 TERI STRATEGY IMPLEMENTATION (PANDAS ENGINE)
# ==============================================================================
# Note: Tumhare indicators (ema, atr, vwap, adx) ka internal pandas math yahan aayega
def calculate_indicators_and_signals(df):
    df = df.copy()
    
    # 1. Base Indicators (Standard pandas implementation for cloud)
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

    # --- Trend, Pullback & Signal Logic (Same as your model) ---
    time_filter = (df.index.time >= dt_time(10, 0)) & (df.index.time <= dt_time(14, 30))
    
    # ADX filter fallback (if internal adx script is not attached, keeping a placeholder or basic math)
    # Yahan hum man ke chal rahe hain aapka custom ADX response 23+ filter clear kar raha hai
    df["ADX"] = 25  # Dummy for cloud structure, actual adx function call can be used here
    
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
    
    long_sl = pd.concat([df["Low"].shift(1), df["Low verso"]], axis=1).min(axis=1) - (0.10 * df["ATR"])
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
# 🤖 AUTOMATED LIVE TRADING ENGINE (PC-LESS RUN)
# ==============================================================================
def run_trading_bot():
    print("🚀 Alpha50 Trading Engine Live & Scanning Dhan Live Data...", flush=True)
    
    # Jin stocks ko trade karna hai unki list
    WATCHLIST = ["NSE_EQ|INFY", "NSE_EQ|RELIANCE", "NSE_EQ|TCS"] 
    
    while True:
        now = datetime.now().time()
        
        # Sirf Market Hours me check karega (9:15 AM to 3:30 PM)
        if dt_time(9, 15) <= now <= dt_time(15, 30):
            for stock in WATCHLIST:
                try:
                    # 1. Dhan API se Last 100 Historical Candles uthao (5-Min interval assume kiya hai)
                    # Dhan API syntax ke according data fetch logic:
                    klines = dhan.get_historical_data(symbol=stock, exchange="NSE", segment="EQUITY", expiry_date="", data_duration="1", instrument_type="")
                    
                    df = pd.DataFrame(klines)
                    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
                    df.set_index('Timestamp', inplace=True)
                    
                    # 2. Strategy Engine me Data dalo
                    processed_df = calculate_indicators_and_signals(df)
                    last_row = processed_df.iloc[-1]
                    
                    # 3. Check for Live Signals
                    if last_row["Signal"] in ["BUY", "SELL"]:
                        print(f"🔥 SIGNAL DETECTED in {stock}: {last_row['Signal']}", flush=True)
                        
                        # Live Google sheet par automatic push
                        log_trade(
                            stock=stock,
                            t_type=last_row["Signal"],
                            e_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            e_price=last_row["Close"], # Execution price
                            sl=last_row["StopLoss"],
                            target=last_row["Target"],
                            qty=10, # Tera preferred size ya position filter logic
                            status="PAPER_LIVE"
                        )
                except Exception as e:
                    print(f"❌ Error monitoring {stock}: {str(e)}", flush=True)
                    
        else:
            print(f"💤 Market Closed. Current time: {datetime.now().strftime('%H:%M:%S')}. Sleeping...", flush=True)
            time.sleep(300) # Market closed hone par 5 minute tak rest karega code
            continue
            
        time.sleep(60) # Live market me har 1 min me scan karega

if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    run_trading_bot()
