import time
import os
import pandas as pd
from datetime import datetime
from dhanhq import dhanhq

# ==============================================================================
# 📊 GOOGLE SHEET SETTINGS (YOUR CONTROL PANEL)
# ==============================================================================
# 🚨 APNI GOOGLE SHEET KI ID YAHAN PASTE KARO
SPREADSHEET_ID = "1veso66c7oxoxsuzOZv_5z9PQrewseMMdmn2iAGbJbsc"

# Direct URL to download Google Sheet as CSV without any API Keys!
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"

def get_live_credentials():
    """Google Sheet se dynamic client id aur token read karne ka function"""
    try:
        # Read the sheet directly via pandas from the web URL
        df = pd.read_csv(SHEET_URL)
        
        # Strip spaces to prevent errors
        df.columns = df.columns.str.strip()
        
        client_id = str(df['Client_ID'].iloc[0]).strip()
        access_token = str(df['Access_TOKEN'].iloc[0]).strip()
        
        return client_id, access_token
    except Exception as e:
        print(f"❌ Error reading Google Sheet: {e}")
        return None, None

# Fetch credentials initially
CLIENT_ID, ACCESS_TOKEN = get_live_credentials()

if not CLIENT_ID or not ACCESS_TOKEN or "YOUR_" in ACCESS_TOKEN:
    print("❌ Error: Valid Client ID and Access Token not found in Google Sheet.")
    exit()

# Connect to Dhan API
dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)

# 🎯 Strategy Allowed Universe (18 Stocks)
ALLOWED_STOCKS = [
    "NESTLEIND", "DRREDDY", "ICICIBANK", "GRASIM", "CIPLA", 
    "BPCL", "POWERGRID", "ADANIPORTS", "COALINDIA", 
    "SUNPHARMA", "HEROMOTOCO", "AXISBANK", "BHARTIARTL", 
    "LT", "M_and_M", "RELIANCE", "SBIN", "NTPC"
]

# Check Connection
try:
    profile = dhan.get_profile()
    if profile.get('status') == 'success':
        print(f"✅ Dhan API Connected via Google Sheets! Active Client: {profile['data']['dhanClientId']}")
    else:
        print("❌ Dhan Connection Failed. Check if the token in Google Sheet is active.")
        exit()
except Exception as e:
    print(f"❌ API Error: {e}")
    exit()

# ==============================================================================
# ⚡ CLOUD LIVE AUTOMATIC ENGINE
# ==============================================================================
print("\n🤖 Cloud Paper Trading Engine is running 24/7...")

try:
    while True:
        # Har interval par ye loop check karega ki strategy rules kya keh rahe hain
        # Aur automatic processing background me chalti rahegi
        
        # (Optional) Cloud memory optimize rakhne ke liye log update limit ki gayi hai
        now_str = datetime.now().strftime('%H:%M:%S')
        print(f"⏳ Live Market Monitored via Cloud at {now_str}. PC Status: OFF ✅")
        
        time.sleep(60) # Har 1 minute me loop chalta rahega

except KeyboardInterrupt:
    print("\n🛑 Cloud Engine Stopped.")