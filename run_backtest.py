import pandas as pd
import numpy as np
import datetime
import time
import os
from strategy_engine import generate_signals

DATA_PATH = "data/historical"

def load_stock(symbol):
    file_path = os.path.join(DATA_PATH, f"{symbol}.csv")
    df = pd.read_csv(file_path)
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df = df.sort_values("Datetime")
    df.set_index("Datetime", inplace=True)
    return df

def run_backtest(df):
    times, signals, entries, stoplosses, targets = df.index.to_pydatetime(), df["Signal"].values, df["Entry"].values, df["StopLoss"].values, df["Target"].values
    highs, lows, closes = df["High"].values, df["Low"].values, df["Close"].values
    trades, position = [], None
    entry_price, stoploss, target, entry_time, trade_type = 0.0, 0.0, 0.0, None, None

    start_time, end_trading_time, squareoff_time = datetime.time(9, 45), datetime.time(15, 0), datetime.time(15, 15)

    for i in range(len(df)):
        current_time = times[i].time()
        
        if position is None:
            if np.isnan(entries[i]) or current_time < start_time or current_time >= end_trading_time: continue
            if signals[i] == "BUY" and entries[i] - stoplosses[i] > 0:
                position, trade_type, entry_price, stoploss, target, entry_time = 1, "LONG", entries[i], stoplosses[i], targets[i], times[i]
            elif signals[i] == "SELL" and stoplosses[i] - entries[i] > 0:
                position, trade_type, entry_price, stoploss, target, entry_time = -1, "SHORT", entries[i], stoplosses[i], targets[i], times[i]
        
        elif position == 1:
            exit_trade, exit_price = False, 0.0
            if lows[i] <= stoploss: exit_price, exit_trade = stoploss, True
            elif highs[i] >= target: exit_price, exit_trade = target, True
            elif current_time >= squareoff_time: exit_price, exit_trade = closes[i], True
            if exit_trade:
                trades.append({"Type": trade_type, "Entry Time": entry_time, "Exit Time": times[i], "Entry": entry_price, "Exit": exit_price, "StopLoss": stoploss, "Target": target, "Quantity": 1, "Points": exit_price - entry_price, "Realized_Profit": exit_price - entry_price})
                position = None
                
        elif position == -1:
            exit_trade, exit_price = False, 0.0
            if highs[i] >= stoploss: exit_price, exit_trade = stoploss, True
            elif lows[i] <= target: exit_price, exit_trade = target, True
            elif current_time >= squareoff_time: exit_price, exit_trade = closes[i], True
            if exit_trade:
                trades.append({"Type": trade_type, "Entry Time": entry_time, "Exit Time": times[i], "Entry": entry_price, "Exit": exit_price, "StopLoss": stoploss, "Target": target, "Quantity": 1, "Points": entry_price - exit_price, "Realized_Profit": entry_price - exit_price})
                position = None

    return pd.DataFrame(trades)

if __name__ == "__main__":
    stocks = [
        "NESTLEIND", "DRREDDY", "ICICIBANK", "GRASIM", "CIPLA", 
        "BPCL", "POWERGRID", "ADANIPORTS", "COALINDIA", 
        "SUNPHARMA", "HEROMOTOCO", "AXISBANK", "BHARTIARTL", 
        "LT", "M_and_M", "RELIANCE", "SBIN", "NTPC"
    ]
    all_raw_trades = []
    print("⏳ Running Backtest...")
    total_start = time.time()
    for stock in stocks:
        try:
            df = load_stock(stock)
            df = generate_signals(df)
            trades = run_backtest(df)
            if len(trades) > 0:
                trades["Stock"] = stock
                all_raw_trades.append(trades)
        except Exception: continue

    print(f"⚡ Done in {time.time() - total_start:.2f}s!")
    if len(all_raw_trades) == 0:
        print("❌ Error: No trades generated.")
        exit()

    master_trades = pd.concat(all_raw_trades, ignore_index=True)
    master_trades["Entry Time"], master_trades["Exit Time"] = pd.to_datetime(master_trades["Entry Time"]), pd.to_datetime(master_trades["Exit Time"])
    master_trades = master_trades.sort_values(by="Entry Time").reset_index(drop=True)
    trade_records = master_trades.to_dict(orient="records")

    INITIAL_CAPITAL, LEVERAGE, MAX_CONCURRENT_TRADES = 100000.0, 4.0, 5
    NORMAL_RISK, RISK_OFF_RISK, DD_TRIGGER_PCT, RECOVERY_PCT = 0.01, 0.003, 0.13, 0.06
    running_capital, peak_capital = INITIAL_CAPITAL, INITIAL_CAPITAL
    active_trades, simulated_trades, risk_off_active = [], [], False

    for trade in trade_records:
        trade_entry_time = trade["Entry Time"]
        exited = [t for t in active_trades if t["Exit Time"] <= trade_entry_time]
        active_trades = [t for t in active_trades if t["Exit Time"] > trade_entry_time]
        
        for ext_t in exited:
            running_capital += ext_t["Realized_Profit"]
            simulated_trades.append(ext_t)
            
        if running_capital > peak_capital: peak_capital = running_capital
        if running_capital <= 0: break

        current_dd = (peak_capital - running_capital) / peak_capital
        if not risk_off_active and current_dd >= DD_TRIGGER_PCT: risk_off_active = True
        elif risk_off_active and current_dd <= RECOVERY_PCT: risk_off_active = False

        if len(active_trades) >= MAX_CONCURRENT_TRADES: continue
        allowed_risk_amt = running_capital * (RISK_OFF_RISK if risk_off_active else NORMAL_RISK)
        unit_risk = (trade["Entry"] - trade["StopLoss"]) if trade["Type"] == "LONG" else (trade["StopLoss"] - trade["Entry"])
        if unit_risk <= 0: continue

        quantity = int(allowed_risk_amt / unit_risk)
        if quantity <= 0: continue

        position_value, total_active_value = trade["Entry"] * quantity, sum(item["Entry"] * item["Quantity"] for item in active_trades)
        if (total_active_value + position_value) > (running_capital * LEVERAGE):
            quantity = int(((running_capital * LEVERAGE) - total_active_value) / trade["Entry"])
            if quantity <= 0: continue

        trade["Quantity"], trade["Realized_Profit"] = quantity, trade["Points"] * quantity
        active_trades.append(trade)

    for act in active_trades:
        running_capital += act["Realized_Profit"]
        simulated_trades.append(act)

    if len(simulated_trades) > 0:
        sim_df = pd.DataFrame(simulated_trades)
        sim_df["Exit Time"] = pd.to_datetime(sim_df["Exit Time"])
        sim_df["Year"] = sim_df["Exit Time"].dt.year
        
        print("\n" + "=" * 80)
        print("📈 UNIFIED PORTFOLIO SIMULATION")
        print("=" * 80)
        print(f"💰 Starting Capital : ₹{INITIAL_CAPITAL:,.2f}")
        print(f"🚀 Final Capital    : ₹{running_capital:,.2f}")
        print(f"🔥 Total Net Profit  : ₹{running_capital - INITIAL_CAPITAL:,.2f} ({((running_capital - INITIAL_CAPITAL)/INITIAL_CAPITAL)*100:.2f}% ROI)")
        print(f"📊 Total Trades taken: {len(sim_df)}")
        print("=" * 80)