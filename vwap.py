import pandas as pd

def vwap(df):

    df = df.copy()

    tp = (df["High"] + df["Low"] + df["Close"]) / 3

    df["VWAP"] = (tp * df["Volume"]).cumsum() / df["Volume"].cumsum()

    return df["VWAP"]