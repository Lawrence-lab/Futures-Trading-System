
import pandas as pd
import numpy as np

def calculate_atr(df, period=10):
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_supertrend(df, period=10, multiplier=3.0):
    if len(df) < period: return None, None
    
    df = df.copy()
    atr = calculate_atr(df, period)
    hl2 = (df['high'] + df['low']) / 2
    
    df['upperband'] = hl2 + (multiplier * atr)
    df['lowerband'] = hl2 - (multiplier * atr)
    df['is_uptrend'] = True
    
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['upperband'].iloc[i-1]:
            df.at[df.index[i], 'is_uptrend'] = True
        elif df['close'].iloc[i] < df['lowerband'].iloc[i-1]:
            df.at[df.index[i], 'is_uptrend'] = False
        else:
            df.at[df.index[i], 'is_uptrend'] = df['is_uptrend'].iloc[i-1]
            
            if df['is_uptrend'].iloc[i] and df['lowerband'].iloc[i] < df['lowerband'].iloc[i-1]:
                df.at[df.index[i], 'lowerband'] = df['lowerband'].iloc[i-1]
            if not df['is_uptrend'].iloc[i] and df['upperband'].iloc[i] > df['upperband'].iloc[i-1]:
                df.at[df.index[i], 'upperband'] = df['upperband'].iloc[i-1]
                
    return df['is_uptrend'].iloc[-1], df['lowerband'].iloc[-1] if df['is_uptrend'].iloc[-1] else df['upperband'].iloc[-1]

def calculate_ut_bot(df, key_value=2, atr_period=10):
    if len(df) < atr_period: return "None"
    
    df = df.copy()
    atr = calculate_atr(df, atr_period)
    df['ema_stop'] = 0.0
    
    # Simple UT Bot logic: Trailing stop based on ATR
    for i in range(1, len(df)):
        src = df['close'].iloc[i]
        loss = key_value * atr.iloc[i]
        
        prev_stop = df['ema_stop'].iloc[i-1]
        if src > prev_stop and df['close'].iloc[i-1] > prev_stop:
            new_stop = max(prev_stop, src - loss)
        elif src < prev_stop and df['close'].iloc[i-1] < prev_stop:
            new_stop = min(prev_stop, src + loss)
        else:
            new_stop = src - loss if src > prev_stop else src + loss
        df.at[df.index[i], 'ema_stop'] = new_stop
        
    current_close = df['close'].iloc[-1]
    prev_close = df['close'].iloc[-2]
    current_stop = df['ema_stop'].iloc[-1]
    
    if current_close > current_stop and prev_close <= df['ema_stop'].iloc[-2]:
        return "Buy"
    elif current_close < current_stop and prev_close >= df['ema_stop'].iloc[-2]:
        return "Sell"
    return "None"

def calculate_bollinger_bands(df, period=20, std_dev=2.5):
    """
    Calculate Bollinger Bands.
    Returns: upper_band (Series), middle_band (Series), lower_band (Series)
    """
    if len(df) < period:
        return None, None, None
    
    close = df['close']
    middle_band = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    
    return upper_band, middle_band, lower_band

def calculate_adx(df, period=14):
    """
    Calculate ADX (Average Directional Index).
    Returns: adx (Series)
    """
    if len(df) < period * 2: return None
    
    high = df['high']
    low = df['low']
    close = df['close']
    
    # 1. TR, +DM, -DM
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    up_move = high - high.shift()
    down_move = low.shift() - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    # 2. Smooth TR, +DM, -DM (Wilder's Smoothing)
    # Wilder's Smoothing is equivalent to EMA with alpha = 1/period? 
    # Or strict Wilder's: prev + (curr - prev)/n ? which is EMA(alpha=1/n).
    # Standard technical libs use alpha=1/n. Pandas ewm(alpha=1/n).
    
    # Using simple rolling for simplicity or EWM? ADX usually uses Wilder's.
    # Let's use EWM with adjust=False, alpha=1/period.
    
    alpha = 1 / period
    
    tr_smooth = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
    
    # 3. Calculate +DI, -DI
    # Avoid division by zero
    tr_smooth = tr_smooth.replace(0, np.nan) # Safety
    plus_di = 100 * (plus_dm_smooth / tr_smooth)
    minus_di = 100 * (minus_dm_smooth / tr_smooth)
    
    # 4. Calculate DX
    sum_di = plus_di + minus_di
    diff_di = abs(plus_di - minus_di)
    
    # Handle division by zero (if sum_di is 0, dx is 0)
    dx = 100 * (diff_di / sum_di.replace(0, np.nan))
    dx = dx.fillna(0)
    
    # 5. Calculate ADX (Smooth DX)
    adx = dx.ewm(alpha=alpha, adjust=False).mean()
    
    return adx
