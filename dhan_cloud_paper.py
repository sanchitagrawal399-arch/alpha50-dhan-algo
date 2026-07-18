# ==============================================================================
# 🎯 STRATEGY CORE RULEBOOK (ALPHA50 WEAPON MATRIX)
# ==============================================================================
# ... (code upar wala same rahega) ...

print("🚀 Alpha50 Strategy Rules Loaded Successfully!")
try:
    # 2.2.0 mein profile access karne ke liye specific controller class ka use karna padega
    # Logs ke mutabik 'TraderControl' naam ki class dikhi thi
    controller = dhanhq.TraderControl(dhan_context=ctx)
    profile = controller.get_profile() # Ye method naam sahi hona chahiye
    
    if profile and profile.get('status') == 'success':
        print(f"✅ Dhan API Securely Authenticated. Active Client: {profile['data']['dhanClientId']}")
    else:
        print("❌ Profile data not found. Checking alternate method...")
        # Fallback agar 'get_profile' ka naam alag hai
        print(profile) 
        exit()
except Exception as e:
    print(f"❌ Dhan API Connection Error: {e}")
    exit()
