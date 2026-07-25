import pandas as pd

def ema(data: pd.Series, period: int):

    """
    Exponential Moving Average
    """

    return data.ewm(
        span=period,
        adjust=False
    ).mean()