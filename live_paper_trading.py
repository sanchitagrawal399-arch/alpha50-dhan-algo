import os
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, time as dtime
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
# 3. STEALTH DATA FETCHER (BYPASSES RATE LIMITS)
# ==========================================
def fetch_stealth_data(stock):
    """Fetches 15-m interval candles directly impersonating Chrome browser"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock}.NS?range=5d&interval=15m"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # impersonate="chrome" tricks Yahoo into thinking this is a real desktop user
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
# 4. LIVE PAPER TRADER ENGINE
# ==========================================
def run_live_tracker():
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist).strftime('%H:%M:%S')
    print(f"\n[{now_ist} IST] 🔄 Checking 15-Min Live Signals...")
    
    for stock in STOCKS:
        try:
            df = fetch_stealth_data(stock)
            time.sleep(1) # Human delay
            
            if df.empty:
                print(f"⚠️ {stock}: Data fetch returned empty.")
                continue
            
            df = generate_signals(df)
            
            last_closed = df.iloc[-2] 
            signal = last_closed.get("Signal", "")
            
            if signal in ["BUY", "SELL"]:
                entry_time = df.index[-2].strftime("%Y-%m-%d %H:%M:%S")
                entry_price = round(float(last_closed["Entry"]), 2)
                trade_type = "LONG" if signal == "BUY" else "SHORT"
                
                print(f"🚨 SIGNAL DETECTED: {stock} | {trade_type} | Entry: ₹{entry_price}")
                
                row_data = [stock, trade_type, entry_time, "-", entry_price, "-", 1, 0.0, "OPEN"]
                
                if sheet:
                    sheet.append_row(row_data)
                    print(f"✅ Trade logged to Trades tab for {stock}")
                else:
                    print("⚠️ Sheet connected nahi hai, log skip hua.")
            else:
                print(f"🔹 {stock}: Checked (No Signal)")
                    
        except Exception as e:
            print(f"❌ Error checking {stock}: {e}")
            continue

# ==========================================
# 5. MAIN SCHEDULER LOOP
# ==========================================
ist = pytz.timezone('Asia/Kolkata')

while True:
    now_ist_dt = datetime.now(ist)
    now_time = now_ist_dt.time()
    
    start_time = dtime(9, 15)
    end_time = dtime(15, 30)
    
    is_weekday = now_ist_dt.weekday() < 5
    
    if is_weekday and (start_time <= now_time <= end_time):
        run_live_tracker()
        print("\n⏳ Waiting 15 minutes for next check...\n")
        time.sleep(900) 
    else:
        print(f"[{now_ist_dt.strftime('%H:%M:%S')} IST] 😴 Market Closed / Weekend. Sleeping for 1 minute...")
        time.sleep(60)
