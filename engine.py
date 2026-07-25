import pandas as pd
import numpy as np

def run_backtest(df):
    # Pure Python Arrays aur NumPy memory allocation use karenge pandas bypass karne ke liye
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

    # Static time comparison values pre-calculate kar lete hain loop ke bahar
    # Isase har loop me string formatting/parsing nahi karni padegi!
    import datetime
    start_time = datetime.time(9, 45)
    end_trading_time = datetime.time(15, 0)
    squareoff_time = datetime.time(15, 15)

    n = len(df)
    
    # Fast numerical array iteration loop
    for i in range(n):
        current_time = times[i].time()

        # ======================================
        # ENTRY LOGIC
        # ======================================
        if position is None:
            # NaN check (numeric helper)
            if np.isnan(entries[i]):
                continue

            # Time boundaries check
            if current_time < start_time or current_time >= end_trading_time:
                continue

            if signals[i] == "BUY":
                initial_risk = entries[i] - stoplosses[i]
                if initial_risk <= 0: 
                    continue

                position = 1  # 1 for LONG
                trade_type = "LONG"
                entry_price = entries[i]
                stoploss = stoplosses[i]
                target = targets[i]
                entry_time = times[i]

            elif signals[i] == "SELL":
                initial_risk = stoplosses[i] - entries[i]
                if initial_risk <= 0: 
                    continue

                position = -1  # -1 for SHORT
                trade_type = "SHORT"
                entry_price = entries[i]
                stoploss = stoplosses[i]
                target = targets[i]
                entry_time = times[i]

        # ======================================
        # LONG EXECUTION LOOP
        # ======================================
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
                    "Quantity": 1,  # Quantity testing portfolio sizing level par evaluate hogi
                    "Points": points,
                    "Profit": points,  # Temporary unit point tracking
                    "Capital": 0.0
                })
                position = None

        # ======================================
        # SHORT EXECUTION LOOP
        # ======================================
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
                    "Quantity": 1,
                    "Points": points,
                    "Profit": points,
                    "Capital": 0.0
                })
                position = None

    return pd.DataFrame(trades)