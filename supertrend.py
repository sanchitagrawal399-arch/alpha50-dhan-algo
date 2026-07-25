import pandas as pd
import numpy as np


def supertrend(df, period=10, multiplier=3):

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

    hl2 = (high + low) / 2

    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr

    final_upper = upperband.copy()
    final_lower = lowerband.copy()

    trend = pd.Series(index=df.index, dtype=int)
    trend.iloc[0] = 1

    for i in range(1, len(df)):

        if close.iloc[i] > final_upper.iloc[i - 1]:
            trend.iloc[i] = 1

        elif close.iloc[i] < final_lower.iloc[i - 1]:
            trend.iloc[i] = -1

        else:

            trend.iloc[i] = trend.iloc[i - 1]

            if trend.iloc[i] == 1:
                final_lower.iloc[i] = max(final_lower.iloc[i], final_lower.iloc[i - 1])

            else:
                final_upper.iloc[i] = min(final_upper.iloc[i], final_upper.iloc[i - 1])

    return trend