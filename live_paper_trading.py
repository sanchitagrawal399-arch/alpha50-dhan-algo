import os
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta, time as dtime
import pytz
import pandas as pd
from curl_cffi import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from strategy_engine import generate_signals

# ==========================================
# 0. DUMMY WEB SERVER FOR RENDER PORT BINDING
# ==========================================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Alpha50 Algo Engine is Running Successfully!")

def run_fake_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_fake_server, daemon=True).start()

print("🚀 Starting Alpha50 Live Paper Trader Script...")

# ==========================================
# 1. GOOGLE SHEETS SETUP
# ==========================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

SHEET_ID = os.getenv("MY_SECRET_SHEET_ID")
CREDS_JSON_ENV = os.getenv("GSPREAD_CREDENTIALS")

sheet = None
try:
    if not SHEET_ID:
        print("❌ Error: 'MY_SECRET_SHEET_ID' environment variable nahi mila!")
    else:
        if CREDS_JSON_ENV:
            creds_dict = json.loads(CREDS_JSON_ENV)
            CREDS = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        elif os.path.exists("credentials.json"):
            CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
        else:
            raise FileNotFoundError("Credentials nahi mile!")

        CLIENT = gspread.authorize(CREDS)
        spreadsheet = CLIENT.open_by_key(SHEET_ID)
        sheet = spreadsheet.worksheet("Trades") 
        print(f"✅ Google Sheets connected successfully! Connected to Tab: '{sheet.title}'")

except Exception as e:
    print(f"❌ Google Sheets Connection Error: {e}")

# ==========================================
# 2. STOCKS LIST
# ==========================================
STOCKS = [
    "NESTLEIND", "DRREDDY", "ICICIBANK", "GRASIM", "CIPLA", 
    "BPCL", "POWERGRID", "ADANIPORTS", "COALINDIA", 
    "SUNPHARMA", "HEROMOTOCO", "AXISBANK", "BHARTIARTL", 
    "LT", "M&M", "RELIANCE", "SBIN", "NTPC"
]

# ==========================================
# 3. HELPER FUNCTIONS FOR POSITION MANAGEMENT
# ==========================================
def get_open_positions():
    """Reads sheet to find currently OPEN positions with SL and Target"""
    if not sheet:
        return {}
    try:
        rows = sheet.get_all_values()
        open_positions = {}
        # Sheet Header: [Stock, Type, Entry_Time, Exit_Time, Entry_Price, Exit_Price, StopLoss, Target, Qty, P&L, Status]
        for idx, row in enumerate(rows[1:], start=2):
            if len(row) >= 11 and row[10].strip().upper() == "OPEN":
                stock = row[0].strip()
                open_positions[stock] = {
                    "row": idx,
                    "type": row[1].strip().upper(),
                    "entry_price": float(row[4]) if row[4] not in ["-", ""] else 0.0,
                    "stop_loss": float(row[6]) if row[6] not in ["-", ""] else 0.0,
                    "target": float(row[7]) if row[7] not in ["-", ""] else 0.0
                }
        return open_positions
    except Exception as e:
        print(f"⚠️ Error fetching open positions: {e}")
        return {}

def close_position(stock, pos_info, exit_price, exit_time, reason="SL/TP"):
    """Closes an active position and updates Google Sheet"""
    if not sheet:
        return
    try:
        row_idx = pos_info["row"]
        entry_price = pos_info["entry_price"]
        trade_type = pos_info["type"]
        qty = 1
        
        if trade_type == "LONG":
            pnl = round((exit_price - entry_price) * qty, 2)
        else:
            pnl = round((entry_price - exit_price) * qty, 2)
            
        sheet.update_cell(row_idx, 4, str(exit_time))   # Exit_Time (Col D)
        sheet.update_cell(row_idx, 6, exit_price)       # Exit_Price (Col F)
        sheet.update_cell(row_idx, 10, pnl)             # P&L (Col J)
        sheet.update_cell(row_idx, 11, f"CLOSED ({reason})") # Status (Col K)
        
        print(f"🔒 CLOSED TRADE [{reason}]: {stock} | {trade_type} | Exit: ₹{exit_price} | P&L: ₹{pnl}")
    except Exception as e:
        print(f"❌ Error closing trade for {stock}: {e}")

# ==========================================
# 4. STEALTH DATA FETCHER
# ==========================================
def fetch_stealth_data(stock):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock}.NS?range=5d&interval=15m"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    res = requests.get(url, headers=headers, impersonate="chrome", timeout=10)
    
    if res.status_code != 200:
        return pd.DataFrame()
        
    data = res.json()
    result = data.get("chart", {}).get("result", [])
    if not result:
        return pd.DataFrame()
        
    timestamps = result[0].get("timestamp", [])
    quote = result[0].get("indicators", {}).get("quote", [{}])[0]
    
    df = pd.DataFrame({
        "Open": quote.get("open", []),
        "High": quote.get("high", []),
        "Low": quote.get("low", []),
        "Close": quote.get("close", []),
        "Volume": quote.get("volume", [])
    }, index=pd.to_datetime(timestamps, unit="s", utc=True))
    
    df.index = df.index.tz_convert("Asia/Kolkata")
    df.dropna(inplace=True)
    return df

# ==========================================
# 5. LIVE PAPER TRADER ENGINE
# ==========================================
def run_live_tracker():
    ist = pytz.timezone('Asia/Kolkata')
    now_dt = datetime.now(ist)
    now_time = now_dt.time()
    print(f"\n[{now_dt.strftime('%H:%M:%S')} IST] 🔄 Executing Candle-Close Engine...")
    
    open_positions = get_open_positions()
    is_intraday_cutoff = now_time >= dtime(15, 15)

    for stock in STOCKS:
        try:
            df = fetch_stealth_data(stock)
            time.sleep(0.5) 
            
            if df.empty:
                print(f"⚠️ {stock}: Data fetch returned empty.")
                continue
            
            df = generate_signals(df)
            
            last_closed = df.iloc[-2] 
            signal = last_closed.get("Signal", "")
            curr_close = round(float(last_closed["Close"]), 2)
            curr_high = round(float(last_closed["High"]), 2)
            curr_low = round(float(last_closed["Low"]), 2)
            curr_time = df.index[-2].strftime("%Y-%m-%d %H:%M:%S")
            
            # --- SCENARIO A: STOCK HAS AN OPEN POSITION ---
            if stock in open_positions:
                pos = open_positions[stock]
                sl_price = pos["stop_loss"]
                tp_price = pos["target"]
                
                # Rule 1: Intraday 3:15 PM Auto-Squareoff
                if is_intraday_cutoff:
                    close_position(stock, pos, curr_close, curr_time, reason="3:15 PM Intraday Cutoff")
                    continue
                
                # Rule 2: Check Target & StopLoss Hits
                sl_hit, tp_hit = False, False
                if pos["type"] == "LONG":
                    if tp_price > 0 and curr_high >= tp_price:
                        tp_hit = True
                    elif sl_price > 0 and curr_low <= sl_price:
                        sl_hit = True
                elif pos["type"] == "SHORT":
                    if tp_price > 0 and curr_low <= tp_price:
                        tp_hit = True
                    elif sl_price > 0 and curr_high >= sl_price:
                        sl_hit = True
                        
                if tp_hit:
                    close_position(stock, pos, tp_price, curr_time, reason="TARGET HIT")
                elif sl_hit:
                    close_position(stock, pos, sl_price, curr_time, reason="STOP LOSS HIT")
                elif (pos["type"] == "LONG" and signal == "SELL") or (pos["type"] == "SHORT" and signal == "BUY"):
                    close_position(stock, pos, curr_close, curr_time, reason="OPPOSITE SIGNAL EXIT")
                else:
                    print(f"🔹 {stock}: Holding {pos['type']} @ ₹{pos['entry_price']} | SL: ₹{sl_price} | TP: ₹{tp_price}")

            # --- SCENARIO B: NO OPEN POSITION FOR THIS STOCK ---
            else:
                if is_intraday_cutoff or now_time >= dtime(15, 0):
                    print(f"🔹 {stock}: Checked (No new entry after 3:00 PM)")
                    continue

                if signal in ["BUY", "SELL"]:
                    trade_type = "LONG" if signal == "BUY" else "SHORT"
                    entry_price = round(float(last_closed.get("Entry", curr_close)), 2)
                    stop_loss = round(float(last_closed.get("StopLoss", 0.0)), 2)
                    target = round(float(last_closed.get("Target", 0.0)), 2)
                    
                    print(f"🚨 NEW SIGNAL: {stock} | {trade_type} | Entry: ₹{entry_price} | SL: ₹{stop_loss} | TP: ₹{target}")
                    
                    # Row: Stock, Type, Entry_Time, Exit_Time, Entry_Price, Exit_Price, StopLoss, Target, Qty, P&L, Status
                    row_data = [stock, trade_type, curr_time, "-", entry_price, "-", stop_loss, target, 1, 0.0, "OPEN"]
                    if sheet:
                        sheet.append_row(row_data)
                        print(f"✅ Trade logged to Trades tab for {stock}")
                else:
                    print(f"🔹 {stock}: Checked (No Signal)")

        except Exception as e:
            print(f"❌ Error checking {stock}: {e}")
            continue

# ==========================================
# 6. DYNAMIC CLOCK-SYNCED SCHEDULER
# ==========================================
def calculate_sleep_seconds(offset_seconds=4):
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    minute_bucket = (now.minute // 15) * 15
    target_dt = now.replace(minute=minute_bucket, second=offset_seconds, microsecond=0)
    
    if now >= target_dt:
        target_dt += timedelta(minutes=15)
        
    if target_dt.time() == dtime(9, 15):
        target_dt += timedelta(minutes=15)
        
    sleep_secs = (target_dt - now).total_seconds()
    return max(1.0, sleep_secs), target_dt

ist = pytz.timezone('Asia/Kolkata')

while True:
    now_ist_dt = datetime.now(ist)
    now_time = now_ist_dt.time()
    
    start_time = dtime(9, 15)
    end_time = dtime(15, 30)
    
    is_weekday = now_ist_dt.weekday() < 5
    
    if is_weekday and (start_time <= now_time <= end_time):
        sleep_secs, next_target = calculate_sleep_seconds(offset_seconds=4)
        print(f"⏰ Next candle check target: {next_target.strftime('%H:%M:%S')} IST (Sleeping {int(sleep_secs)}s)...")
        time.sleep(sleep_secs)
        run_live_tracker()
    else:
        print(f"[{now_ist_dt.strftime('%H:%M:%S')} IST] 😴 Market Closed / Weekend. Sleeping for 1 minute...")
        time.sleep(60)
