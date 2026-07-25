import pandas as pd
import numpy as np
import time
import datetime

from src.data_loader import load_stock

# ==============================================================================
# 📈 EXACT PURE PANDAS MATH ENGINE
# ==============================================================================
def calculate_adx_components(df, periods=14):
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    tr1 = high - low
    tr2 = np.abs(high - close.shift(1))
    tr3 = np.abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    up_move = high.diff()
    down_move = -low.diff()
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    atr_smooth = tr.ewm(alpha=1/periods, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1/periods, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1/periods, adjust=False).mean() / atr_smooth)
    
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx_series = dx.ewm(alpha=1/periods, adjust=False).mean()
    
    return adx_series, plus_di, minus_di

def generate_signals(df):
    df = df.copy()

    # Indicators
    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()
    
    high_low = df['High'] - df['Low']
    high_cp = np.abs(df['High'] - df['Close'].shift())
    low_cp = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1).rolling(window=14).mean()
    
    df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    df["VOL20"] = df["Volume"].rolling(window=20).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    df["ADX"], df["PLUS_DI"], df["MINUS_DI"] = calculate_adx_components(df, 14)

    # Time Filter
    time_filter = (
        (df.index.time >= pd.to_datetime("10:00").time()) &
        (df.index.time <= pd.to_datetime("14:30").time())
    )

    # Trend Filter
    long_trend = (
        (df["Close"] > df["VWAP"]) &
        (df["EMA9"] > df["EMA21"]) &
        (df["ADX"] >= 23) &
        (df["PLUS_DI"] > df["MINUS_DI"])
    )

    short_trend = (
        (df["Close"] < df["VWAP"]) &
        (df["EMA9"] < df["EMA21"]) &
        (df["ADX"] >= 23) &
        (df["PLUS_DI"] < df["MINUS_DI"])
    )

    # Pullback Candle
    pullback_buy = (
        long_trend &
        (df["Low"] <= df["EMA9"]) &
        (df["Close"] > df["EMA21"]) &
        (df["RSI"] >= 40) &
        (df["RSI"] <= 60)
    )

    pullback_sell = (
        short_trend &
        (df["High"] >= df["EMA9"]) &
        (df["Close"] < df["EMA21"]) &
        (df["RSI"] >= 40) &
        (df["RSI"] <= 60)
    )

    pullback_buy_window = pullback_buy.rolling(window=3, min_periods=1).sum() > 0
    pullback_sell_window = pullback_sell.rolling(window=3, min_periods=1).sum() > 0

    # Signal Candle
    buy = (
        pullback_buy_window.shift(1).fillna(False) &
        (df["Close"] > df["EMA9"]) &
        (df["RSI"] > df["RSI"].shift(1)) &
        (df["Volume"] >= df["VOL20"]) &
        time_filter
    )

    sell = (
        pullback_sell_window.shift(1).fillna(False) &
        (df["Close"] < df["EMA9"]) &
        (df["RSI"] < df["RSI"].shift(1)) &
        (df["Volume"] >= df["VOL20"]) &
        time_filter
    )

    df["Signal"] = ""
    df.loc[buy, "Signal"] = "BUY"
    df.loc[sell, "Signal"] = "SELL"

    df["Entry"] = df["Open"].shift(-1)

    df["RR_Multiplier"] = np.where(
        df["ADX"] >= 35, 2.8,
        np.where(df["ADX"] >= 23, 1.8, 1.2)
    )

    long_sl_series = pd.concat([df["Low"].shift(1), df["Low"]], axis=1).min(axis=1) - (0.10 * df["ATR"])
    short_sl_series = pd.concat([df["High"].shift(1), df["High"]], axis=1).max(axis=1) + (0.10 * df["ATR"])

    df["StopLoss"] = np.nan
    df["Target"] = np.nan

    for idx in df[buy].index:
        entry_val = df.loc[idx, "Entry"]
        sl_val = long_sl_series.loc[idx]
        rr_val = df.loc[idx, "RR_Multiplier"]
        risk = entry_val - sl_val
        if risk > 0:
            df.loc[idx, "StopLoss"] = sl_val
            df.loc[idx, "Target"] = entry_val + (risk * rr_val)

    for idx in df[sell].index:
        entry_val = df.loc[idx, "Entry"]
        sl_val = short_sl_series.loc[idx]
        rr_val = df.loc[idx, "RR_Multiplier"]
        risk = sl_val - entry_val
        if risk > 0:
            df.loc[idx, "StopLoss"] = sl_val
            df.loc[idx, "Target"] = entry_val - (risk * rr_val)

    return df

# ==============================================================================
# 🎯 EXACT BACKTEST ENGINE
# ==============================================================================
def run_backtest(df):
    times = df.index.to_pydatetime()
    signals = df["Signal"].values
    entries = df["Entry"].values
    stoplosses = df["StopLoss"].values
    targets = df["Target"].values
    highs = df["High"].values
    lows = df["Low"].values
    closes = df["Close"].values

    trades = []
    position = None

    entry_price = 0.0
    stoploss = 0.0
    target = 0.0
    entry_time = None
    trade_type = None

    start_time = datetime.time(9, 45)
    end_trading_time = datetime.time(15, 0)
    squareoff_time = datetime.time(15, 15)

    n = len(df)
    
    for i in range(n):
        current_time = times[i].time()

        if position is None:
            if pd.isna(entries[i]):
                continue

            if current_time < start_time or current_time >= end_trading_time:
                continue

            if signals[i] == "BUY":
                initial_risk = entries[i] - stoplosses[i]
                if initial_risk <= 0: 
                    continue

                position = 1 
                trade_type = "LONG"
                entry_price = entries[i]
                stoploss = stoplosses[i]
                target = targets[i]
                entry_time = times[i]

            elif signals[i] == "SELL":
                initial_risk = stoplosses[i] - entries[i]
                if initial_risk <= 0: 
                    continue

                position = -1 
                trade_type = "SHORT"
                entry_price = entries[i]
                stoploss = stoplosses[i]
                target = targets[i]
                entry_time = times[i]

        elif position == 1:
            exit_trade = False
            exit_price = 0.0

            if lows[i] <= stoploss:
                exit_price = stoploss
                exit_trade = True
            elif highs[i] >= target:
                exit_price = target
                exit_trade = True
            elif current_time >= squareoff_time:
                exit_price = closes[i]
                exit_trade = True

            if exit_trade:
                points = exit_price - entry_price
                trades.append({
                    "Type": trade_type,
                    "Entry Time": entry_time,
                    "Exit Time": times[i],
                    "Entry": entry_price,
                    "Exit": exit_price,
                    "StopLoss": stoploss,
                    "Target": target,
                    "Points": points
                })
                position = None

        elif position == -1:
            exit_trade = False
            exit_price = 0.0

            if highs[i] >= stoploss:
                exit_price = stoploss
                exit_trade = True
            elif lows[i] <= target:
                exit_price = target
                exit_trade = True
            elif current_time >= squareoff_time:
                exit_price = closes[i]
                exit_trade = True

            if exit_trade:
                points = entry_price - exit_price
                trades.append({
                    "Type": trade_type,
                    "Entry Time": entry_time,
                    "Exit Time": times[i],
                    "Entry": entry_price,
                    "Exit": exit_price,
                    "StopLoss": stoploss,
                    "Target": target,
                    "Points": points
                })
                position = None

    return pd.DataFrame(trades)

# ==============================================================================
# 🎯 EXECUTION AND PORTFOLIO ENGINE
# ==============================================================================
if __name__ == "__main__":
    stocks = [
        "NESTLEIND", "DRREDDY", "ICICIBANK", "GRASIM", "CIPLA", 
        "BPCL", "POWERGRID", "ADANIPORTS", "COALINDIA", 
        "SUNPHARMA", "HEROMOTOCO", "AXISBANK", "BHARTIARTL", 
        "LT", "M_and_M", "RELIANCE", "SBIN", "NTPC"
    ]

    all_raw_trades = []
    print("⏳ Running Backtest with Sync Fix...")
    total_start = time.time()

    for stock in stocks:
        try:
            df = load_stock(stock)
            df = generate_signals(df)
            trades = run_backtest(df)

            if len(trades) == 0:
                continue

            trades["Stock"] = stock
            all_raw_trades.append(trades)
        except Exception:
            continue

    print(f"⚡ Backtest completed in {time.time() - total_start:.2f}s!")

    if len(all_raw_trades) == 0:
        print("❌ Error: No trades generated.")
        exit()

    master_trades = pd.concat(all_raw_trades, ignore_index=True)
    master_trades["Entry Time"] = pd.to_datetime(master_trades["Entry Time"])
    master_trades["Exit Time"] = pd.to_datetime(master_trades["Exit Time"])
    master_trades = master_trades.sort_values(by="Entry Time").reset_index(drop=True)
    trade_records = master_trades.to_dict(orient="records")

    INITIAL_CAPITAL = 100000.0   
    LEVERAGE = 4.0               
    MAX_CONCURRENT_TRADES = 5   

    NORMAL_RISK = 0.01          
    RISK_OFF_RISK = 0.003       
    DD_TRIGGER_PCT = 0.13       
    RECOVERY_PCT = 0.06         

    running_capital = INITIAL_CAPITAL
    peak_capital = INITIAL_CAPITAL
    active_trades = []          
    simulated_trades = []       
    risk_off_active = False

    for trade in trade_records:
        trade_entry_time = trade["Entry Time"]
        
        exited = [t for t in active_trades if t["Exit Time"] <= trade_entry_time]
        still_active = [t for t in active_trades if t["Exit Time"] > trade_entry_time]
        
        for ext_t in exited:
            running_capital += ext_t["Realized_Profit"]
            simulated_trades.append(ext_t)
            
        active_trades = still_active

        if running_capital > peak_capital:
            peak_capital = running_capital

        if running_capital <= 0:
            print("🚨 Portfolio Bankrupt!")
            break

        current_dd = (peak_capital - running_capital) / peak_capital
        
        if not risk_off_active and current_dd >= DD_TRIGGER_PCT:
            risk_off_active = True
        elif risk_off_active and current_dd <= RECOVERY_PCT:
            risk_off_active = False

        current_risk_multiplier = RISK_OFF_RISK if risk_off_active else NORMAL_RISK

        if len(active_trades) >= MAX_CONCURRENT_TRADES:
            continue
            
        allowed_risk_amt = running_capital * current_risk_multiplier
        unit_risk = (trade["Entry"] - trade["StopLoss"]) if trade["Type"] == "LONG" else (trade["StopLoss"] - trade["Entry"])

        if unit_risk <= 0:
            continue

        quantity = int(allowed_risk_amt / unit_risk)
        if quantity <= 0:
            continue

        position_value = trade["Entry"] * quantity
        total_active_value = sum(item["Entry"] * item["Quantity"] for item in active_trades)
        
        if (total_active_value + position_value) > (running_capital * LEVERAGE):
            max_allowed_val = (running_capital * LEVERAGE) - total_active_value
            quantity = int(max_allowed_val / trade["Entry"])
            if quantity <= 0:
                continue

        trade["Quantity"] = quantity
        trade["Realized_Profit"] = trade["Points"] * quantity
        trade["Risk_Mode"] = "Risk-Off" if risk_off_active else "Normal"
        active_trades.append(trade)

    for act in active_trades:
        running_capital += act["Realized_Profit"]
        simulated_trades.append(act)

    if len(simulated_trades) > 0:
        sim_df = pd.DataFrame(simulated_trades)
        sim_df["Exit Time"] = pd.to_datetime(sim_df["Exit Time"])
        sim_df["Year"] = sim_df["Exit Time"].dt.year
        
        print("\n" + "=" * 80)
        print("📈 UNIFIED PORTFOLIO SIMULATION (EXACT MATCH FOR LIVE BOT)")
        print("=" * 80)
        print(f"💰 Starting Capital : ₹{INITIAL_CAPITAL:,.2f}")
        print(f"🚀 Final Capital    : ₹{running_capital:,.2f}")
        print(f"🔥 Total Net Profit  : ₹{running_capital - INITIAL_CAPITAL:,.2f} ({((running_capital - INITIAL_CAPITAL)/INITIAL_CAPITAL)*100:.2f}% ROI)")
        print(f"⚡ Margin Multiplier : {LEVERAGE}x (Max Buying Power: ₹{INITIAL_CAPITAL * LEVERAGE:,.2f})")
        print(f"📊 Total Trades taken: {len(sim_df)}")
        print("=" * 80)
        
        print("\n" + "=" * 60)
        print("📅 YEAR-WISE COMBINED PORTFOLIO PERFORMANCE (NET PROFIT)")
        print("=" * 60)
        
        year_summary = sim_df.groupby("Year").agg(
            Trades_Taken=('Realized_Profit', 'count'),
            Net_Profit=('Realized_Profit', 'sum'),
        ).reset_index()
        
        year_summary["Net_Profit"] = year_summary["Net_Profit"].round(2)
        print(year_summary.to_string(index=False))
        print("=" * 60)
    else:
        print("❌ No trades simulated.")