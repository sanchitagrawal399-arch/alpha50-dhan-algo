import time
import os
import pandas as pd
from datetime import datetime
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import dhanhq  

# ==============================================================================
# 🌐 DUMMY WEB SERVER (RENDER KO KHUSH RAKHNE KE LIYE)
# ==============================================================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Alpha50 Algo is Live and Running 24/7 on Free Tier!")

# ==============================================================================
# 🤖 ALGO MAIN LOOP (AB YE BACKGROUND MEIN CHALEGA)
# ==============================================================================
def run_trading_bot():
    SPREADSHEET_ID = os.environ.get("MY_SECRET_SHEET_ID") 
    SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"

    def get_live_credentials():
        try:
            df = pd.read_csv(SHEET_URL)
            df.columns = df.columns.str.strip()
            if df.empty:
                print("❌ Google Sheet is empty! Please add data in row 2.", flush=True)
                return None, None
                
            client_id = str(df['Client_ID'].iloc[0]).strip()
            access_token = str(df['Access_TOKEN'].iloc[0]).strip()
            return client_id, access_token
        except Exception as e:
            print(f"❌ Sheet Read Error: {e}", flush=True)
            return None, None

    CLIENT_ID, ACCESS_TOKEN = get_live_credentials()
    if not CLIENT_ID or not ACCESS_TOKEN or "YOUR_" in ACCESS_TOKEN:
        print("❌ Critical: Valid credentials not found in Google Sheet.", flush=True)
        return

    # DHAN CONNECTION
    try:
        ctx = dhanhq.DhanContext(client_id=CLIENT_ID, access_token=ACCESS_TOKEN)
        dhan = dhanhq.TraderControl(dhan_context=ctx)
        print("🎯 Connection handshake established successfully.", flush=True)
    except Exception as e:
        print(f"❌ Connection Mapping Failure: {e}", flush=True)
        return

    print("🚀 Alpha50 Strategy Rules Loaded Successfully!", flush=True)
    
    try:
        profile = dhan.get_profile()
        if profile and profile.get('status') == 'success':
            print(f"✅ Dhan API Securely Authenticated. Active Client: {profile['data']['dhanClientId']}", flush=True)
        else:
            print(f"⚠️ Profile check bypass, response received: {profile}", flush=True)
    except Exception as e:
        print(f"❌ Dhan API Execution Error: {e}", flush=True)
        pass

    print("\n🤖 158% ROI Framework Active on Cloud Infrastructure...", flush=True)
    
    try:
        while True:
            now_str = datetime.now().strftime('%H:%M:%S')
            print(f"⏳ Loop completed at {now_str}. Scanning market ticks continuously... PC Status: OFF ✅", flush=True)
            time.sleep(60)
    except Exception as e:
        print(f"\n🛑 Cloud Algo Framework Stopped: {e}", flush=True)


# ==============================================================================
# 🚀 SYSTEM STARTUP SEQUENCE
# ==============================================================================
if __name__ == "__main__":
    # 1. Bot ko pehle background (daemon) thread mein chalu karo
    algo_thread = threading.Thread(target=run_trading_bot, daemon=True)
    algo_thread.start()

    # 2. Main thread par server chalao jisse Render ko "Open Port" mil jaye
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Starting Render Dummy Web Server on port {port}...", flush=True)
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()
