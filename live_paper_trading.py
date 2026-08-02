import os
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, time as dtime
import pytz
import pandas as pd
import yfinance as yf
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
        elif os.path.exists("/etc/secrets/credentials.json"):
            CREDS = ServiceAccountCredentials.from_json_keyfile_name("/etc/secrets/credentials.json", SCOPE)
        else:
            raise FileNotFoundError("Na 'credentials.json' file mili na 'GSPREAD_CREDENTIALS' env variable!")

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
# 3. LIVE PAPER TRADER ENGINE
# ==========================================
def run_live_tracker():
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist).strftime('%H:%M:%S')
    print(f"\n[{now_ist} IST] 🔄 Checking 15-Min Live Signals on yfinance...")
    
    success_count = 0
    signal_count = 0

    for stock in STOCKS:
        try:
            yf_symbol = f"{stock}.NS"
            
            # Use Ticker history for cleaner fetching
            ticker_obj = yf.Ticker(yf_symbol)
            df = ticker_obj.history(period="5d", interval="15m")
            
            if df.empty:
                print(f"⚠️ {stock}: No data received (possible rate-limit).")
                time.sleep(3)  # Extra delay if empty
                continue
                
            success_count += 1
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            
            df.index = pd.to_datetime(df.index)
            df = generate_signals(df)
            
            last_closed = df.iloc[-2] 
            signal = last_closed.get("Signal", "")
            
            if signal in ["BUY", "SELL"]:
                signal_count += 1
                entry_time = df.index[-2].strftime("%Y-%m-%d %H:%M:%S")
                entry_price = round(float(last_closed["Entry"]), 2)
                trade_type = "LONG" if signal == "BUY" else "SHORT"
                
                exit_time = "-"
                exit_price = "-"
                quantity = 1  
                pnl = 0.0
                status = "OPEN"
                
                print(f"🚨 SIGNAL DETECTED: {stock} | {trade_type} | Entry: ₹{entry_price}")
                
                row_data = [
                    stock, trade_type, entry_time, exit_time, 
                    entry_price, exit_price, quantity, pnl, status
                ]
                
                if sheet:
                    sheet.append_row(row_data)
                    print(f"✅ Trade logged to Google Sheet for {stock}")
                else:
                    print("⚠️ Sheet connected nahi hai, data push fail hua.")
            
            # Anti-Rate-Limit Delay between each stock check
            time.sleep(2.5)
                    
        except Exception as e:
            print(f"⚠️ Error checking {stock}: {e}")
            time.sleep(3)
            continue

    print(f"📊 Scan Summary: {success_count}/{len(STOCKS)} stocks fetched successfully | Signals Found: {signal_count}")

# ==========================================
# 4. MAIN SCHEDULER LOOP (WITH IST TIMEZONE)
# ==========================================
ist = pytz.timezone('Asia/Kolkata')

while True:
    now_ist_dt = datetime.now(ist)
    now_time = now_ist_dt.time()
    
    start_time = dtime(9, 15)
    end_time = dtime(15, 30)
    
    # Check weekday (0 = Monday, ..., 4 = Friday)
    is_weekday = now_ist_dt.weekday() < 5
    
    if is_weekday and (start_time <= now_time <= end_time):
        run_live_tracker()
        print("⏳ Waiting 15 minutes for next candle close...\n")
        time.sleep(900) 
    else:
        print(f"[{now_ist_dt.strftime('%H:%M:%S')} IST] 😴 Market Closed / Weekend. Sleeping for 1 minute...")
        time.sleep(60)
