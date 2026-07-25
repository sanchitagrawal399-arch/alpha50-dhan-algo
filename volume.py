def volume_ma(volume, period=20):
    return volume.rolling(period).mean()