import sys, os, threading, time, requests, pandas as pd, numpy as np, dhanhq
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

# ==============================================================================
# 📊 GOOGLE SHEET CREDENTIAL LOADER (THE "SHEET-FIRST" METHOD)
# ==============================================================================
def get_credentials():
    sheet_id = os.environ.get("MY_SECRET_SHEET_ID")
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        client_id = str(df['Client_ID'].iloc[0]).strip()
        access_token = str(df['Access_TOKEN'].iloc[0]).strip()
        return client_id, access_token
    except Exception as e:
        print(f"❌ Error fetching from Sheet: {e}", flush=True)
        return None, None

# ==============================================================================
# 🤖 BOT LOOP
# ==============================================================================
def run_trading_bot():
    print("🚀 Alpha50 Sheet-First Engine Initialized...", flush=True)
    
    # Credentials sheet se utha rahe hain
    cid, token = get_credentials()
    
    if not cid or not token:
        print("❌ Critical: Credentials could not be loaded from Google Sheet!", flush=True)
        return

    try:
        ctx = dhanhq.DhanContext(client_id=cid, access_token=token)
        dhan = dhanhq.TraderControl(dhan_context=ctx)
        print("✅ Connection Established via Google Sheet Credentials!", flush=True)
    except Exception as e:
        print(f"❌ Connection Error: {e}", flush=True)
        return

    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring Market...", flush=True)
        time.sleep(300)

# ==============================================================================
# 🌐 LAUNCHER
# ==============================================================================
if __name__ == "__main__":
    threading.Thread(target=run_trading_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 10000))
    HTTPServer(('0.0.0.0', port), lambda *args: BaseHTTPRequestHandler(*args)).serve_forever()
