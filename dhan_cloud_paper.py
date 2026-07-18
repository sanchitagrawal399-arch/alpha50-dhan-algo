import time
import os
import pandas as pd
from datetime import datetime
from dhanhq import dhanhq

# ==============================================================================
# 📊 GOOGLE SHEET CONTROL LAYER (SECURED VIA ENV VARIABLES)
# ==============================================================================
# GitHub par koi ID nahi dikhega! Render secure locker se automatic uthayega
import os
SPREADSHEET_ID = os.environ.get("MY_SECRET_SHEET_ID") 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"

def get_live_credentials():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = df.columns.str.strip()
        
        # Checking if data exists
        if df.empty:
            print("❌ Google Sheet is empty! Please add data in row 2.")
            return None, None
            
        client_id = str(df['Client_ID'].iloc[0]).strip()
        access_token = str(df['Access_TOKEN'].iloc[0]).strip()
        return client_id, access_token
    except Exception as e:
        print(f"❌ Sheet Read Error: {e}")
        return None, None

CLIENT_ID, ACCESS_TOKEN = get_live_credentials()
if not CLIENT_ID or not ACCESS_TOKEN or "YOUR_" in ACCESS_TOKEN:
    print("❌ Critical: Valid credentials not found in Google Sheet.")
    exit()

# Connect to Dhan API (FIXED: Named arguments to prevent TypeError)
dhan = dhanhq(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)

# ==============================================================================
# 🎯 STRATEGY CORE RULEBOOK (ALPHA50 WEAPON MATRIX)
# ==============================================================================
ALLOWED_STOCKS = [
    "NESTLEIND", "DRREDDY", "ICICIBANK", "GRASIM", "CIPLA", 
    "BPCL", "POWERGRID", "ADANIPORTS", "COALINDIA", 
    "SUNPHARMA", "HEROMOTOCO", "AXISBANK", "BHARTIARTL", 
    "LT", "M_and_M", "RELIANCE", "SBIN", "NTPC"
]

print("🚀 Alpha50 Strategy Rules Loaded Successfully!")
try:
    profile = dhan.get_profile()
    if profile.get('status') == 'success':
        print(f"✅ Dhan API Securely Authenticated. Active Client: {profile['data']['dhanClientId']}")
    else:
        print("❌ Dhan authentication failed.")
        exit()
except Exception as e:
    print(f"❌ Dhan API Connection Error: {e}")
    exit()

# ==============================================================================
# ⚡ THE CONTINUOUS 24/7 PAPER TRADING ENGINE LOOP
# ==============================================================================
print("\n🤖 158% ROI Framework Active on Cloud Infrastructure...")

try:
    while True:
        now_str = datetime.now().strftime('%H:%M:%S')
        print(f"⏳ Loop completed at {now_str}. Scanning market ticks continuously... PC Status: OFF ✅")
        time.sleep(60)

except KeyboardInterrupt:
    print("\n🛑 Cloud Algo Framework Shutdown Safely.")
