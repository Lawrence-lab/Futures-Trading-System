
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
