import sys
import os
import itertools
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

# Add project root to system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.connection import Trader
from src.strategies.dual_logic import DualTimeframeStrategy
from src.strategies.indicators import calculate_atr, calculate_supertrend

# Disable Line notifications during backtest to prevent spam
os.environ["DISABLE_LINE_NOTIFY"] = "true"

# 禁用策略中的 logging 輸出，避免洗版
logging.getLogger().setLevel(logging.CRITICAL)

def get_historical_data(trader, contract, days=180):
    print(f"Fetching historical data for {contract.code} (Last {days} days)...")
    now = datetime.now()
    start_date = (now - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    
    kbars = trader.api.kbars(contract=contract, start=start_date, end=end_date)
    
    df_1m = pd.DataFrame({
        'ts': pd.to_datetime(kbars.ts),
        'open': kbars.Open,
        'high': kbars.High,
        'low': kbars.Low,
        'close': kbars.Close,
        'volume': kbars.Volume
    })
    
    if df_1m.empty: return None, None
        
    df_1m.rename(columns={'ts': 'datetime'}, inplace=True)
    df_1m.set_index('datetime', inplace=True)
    
    ohlc_dict = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
    df_60m = df_1m.resample('60min', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
    df_1d = df_1m.resample('1D', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
    
    # Pre-calculate 1D trend to speed up backtest
    from src.strategies.indicators import calculate_atr
    
    def get_supertrend_series(df, period=10, multiplier=3.0):
        if len(df) < period: return pd.Series([False]*len(df), index=df.index)
        df = df.copy()
        atr = calculate_atr(df, period)
        hl2 = (df['high'] + df['low']) / 2
        df['upperband'] = hl2 + (multiplier * atr)
        df['lowerband'] = hl2 - (multiplier * atr)
        
        close = df['close'].values
        upper = df['upperband'].values
        lower = df['lowerband'].values
        trend = np.ones(len(df), dtype=bool)
        
        for i in range(1, len(df)):
            if close[i] > upper[i-1]: trend[i] = True
            elif close[i] < lower[i-1]: trend[i] = False
            else:
                trend[i] = trend[i-1]
                if trend[i] and lower[i] < lower[i-1]: lower[i] = lower[i-1]
                if not trend[i] and upper[i] > upper[i-1]: upper[i] = upper[i-1]
        return pd.Series(trend, index=df.index)

    df_1d['is_uptrend'] = get_supertrend_series(df_1d)
    df_60m['atr'] = calculate_atr(df_60m)
    
    return df_60m, df_1d

def get_ut_bot_series(df, key_value=2.0, atr_period=10):
    if len(df) < atr_period: return pd.Series(["None"]*len(df), index=df.index)
    atr = df['atr'].values if 'atr' in df.columns else calculate_atr(df, atr_period).values
    ema_stop = np.zeros(len(df))
    close = df['close'].values
    signal = np.array(["None"] * len(df), dtype=object)
    
    for i in range(1, len(df)):
        src = close[i]
        loss = key_value * atr[i]
        prev_stop = ema_stop[i-1]
        
        if src > prev_stop and close[i-1] > prev_stop:
            new_stop = max(prev_stop, src - loss)
        elif src < prev_stop and close[i-1] < prev_stop:
            new_stop = min(prev_stop, src + loss)
        else:
            new_stop = src - loss if src > prev_stop else src + loss
        ema_stop[i] = new_stop
        
    current_stops = ema_stop
    prev_stops = np.roll(ema_stop, 1)
    prev_closes = np.roll(close, 1)
    
    buy_cond = (close > current_stops) & (prev_closes <= prev_stops)
    sell_cond = (close < current_stops) & (prev_closes >= prev_stops)
    
    signal[buy_cond] = "Buy"
    signal[sell_cond] = "Sell"
    
    return pd.Series(signal, index=df.index)

def run_simulation(df_60m, df_1d, ut_key, trailing_drop):
    strategy = DualTimeframeStrategy(name="Gatekeeper-MXF-V1_Opt", portfolio=None, contract=None)
    
    # Apply parameters
    strategy.ut_bot_key = ut_key
    strategy.trailing_stop_drop = trailing_drop
    
    # Pre-calc UT-BOT for this specific key
    df_60m = df_60m.copy()
    df_60m['signal'] = get_ut_bot_series(df_60m, key_value=ut_key)
    
    times_1d = df_1d['datetime'].values
    
    for i in range(len(df_60m)):
        sig_60m = df_60m['signal'].iloc[i]
        current_time = df_60m.iloc[i]['datetime']
        
        target_time = current_time.to_datetime64() if isinstance(current_time, pd.Timestamp) else current_time
        prev_1d = target_time - np.timedelta64(1440, 'm')
        idx_safe = np.searchsorted(times_1d, prev_1d, side='right') - 1
        
        is_bull_1d = False if idx_safe < 0 else df_1d['is_uptrend'].iloc[idx_safe]

        df_60m_row = df_60m.iloc[[i]]
        df_1d_dummy = df_1d.iloc[[0]] 
        
        strategy.check_signals(
            df_60m_row, 
            df_1d_dummy, 
            precalc_bullish_1d=is_bull_1d, 
            precalc_signal_60m=sig_60m
        )
            
    trades = strategy.trades
    total_trades = len(trades)
    if total_trades == 0:
        return 0, 0, 0
        
    wins = [t for t in trades if t['pnl'] > 0]
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = (len(wins) / total_trades) * 100
    
    return total_trades, win_rate, total_pnl

def main():
    print("Initializing MXF Dual-Logic Parameter Optimization...")
    trader = Trader()
    trader.login()
    print("Login successful.")

    tmf_contracts = [c for c in trader.api.Contracts.Futures.TMF if c.code[-2:] not in ["R1", "R2"] and c.delivery_date != ""]
    if not tmf_contracts:
        print("No TMF contracts found.")
        return
    tmf_contracts.sort(key=lambda x: x.delivery_date)
    target_contract = tmf_contracts[0]

    df_60m, df_1d = get_historical_data(trader, target_contract, days=180)
    if df_60m is None or df_60m.empty:
        print("Failed to fetch historical data.")
        return
        
    print(f"60m Bars: {len(df_60m)}")

    # 要測試的參數組合 (Grid Search)
    # UT Bot Key 從 2.5 到 4.5
    ut_keys = [2.5, 3.0, 3.5, 4.0, 4.5]
    
    # 移動停利折返點數 從 50 到 200
    trailing_drops = [50, 100, 150, 200]
    
    results = []
    total_combinations = len(ut_keys) * len(trailing_drops)
    current_idx = 1
    
    print("-" * 65)
    print(f"{'UT-Bot Key':>10} | {'Trail Drop':>10} | {'Trades':>8} | {'Win Rate %':>12} | {'Total PnL':>10}")
    print("-" * 65)

    for ut_k, t_drop in itertools.product(ut_keys, trailing_drops):
        sys.stdout.write(f"\rEvaluating {current_idx}/{total_combinations}...")
        sys.stdout.flush()
        
        trades_count, win_rate, pnl = run_simulation(df_60m, df_1d, ut_k, t_drop)
        
        results.append({
            'UT_Key': ut_k,
            'Trail_Drop': t_drop,
            'Trades': trades_count,
            'Win_Rate': win_rate,
            'PnL': pnl
        })
        current_idx += 1
        
    print("\n" + "-" * 65)
    
    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values(by='PnL', ascending=False).reset_index(drop=True)
    
    for idx, row in res_df.iterrows():
        print(f"{row['UT_Key']:>10.1f} | {row['Trail_Drop']:>10.0f} | {int(row['Trades']):>8d} | {row['Win_Rate']:>11.2f}% | {row['PnL']:>10.1f}")

    best_setup = res_df.iloc[0]
    print("-" * 65)
    # Fix encoding issue for Windows CMD
    print(f"Best MXF Setup: UT Key {best_setup['UT_Key']}, Trailing Drop {int(best_setup['Trail_Drop'])} pts")
    print(f"=> Expected PnL: {best_setup['PnL']}, Trades: {int(best_setup['Trades'])}")

if __name__ == "__main__":
    main()
