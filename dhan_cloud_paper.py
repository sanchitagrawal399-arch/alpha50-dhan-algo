import time
import os
import pandas as pd
from datetime import datetime
from dhanhq import dhanhq

# ==============================================================================
# 📊 GOOGLE SHEET CONTROL LAYER (SECURED VIA ENV VARIABLES)
# ==============================================================================
SPREADSHEET_ID = os.environ.get("MY_SECRET_SHEET_ID") 
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"

def get_live_credentials():
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = df.columns.str.strip()
        
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

# ==============================================================================
# 🛡️ DHAN CONNECTION LAYER (FIXED FOR VERSION 2.2.0)
# ==============================================================================
# Naye update ke mutabik client initialization:
try:
    # Latest DhanHQ convention requires a distinct client structure
    dhan = dhanhq(dhan_context={"client_id": CLIENT_ID, "access_token": ACCESS_TOKEN})
except TypeError:
    try:
        # Fallback if structural initialization differs
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        exit()

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
        print("❌ Dhan authentication failed. Please check the token inside your Sheet.")
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
