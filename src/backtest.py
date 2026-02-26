
"""
Backtesting script for DualTimeframeStrategy.
Fetches historical 1-minute data, resamples to 5m and 60m, and runs the strategy simulation.
"""
import sys
import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project root to system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.connection import Trader
from src.strategies.dual_logic import DualTimeframeStrategy
import logging

# Configure logging to show strategy output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    print("Initializing Backtest...")
    
    # 1. Login
    trader = Trader()
    trader.login()
    print("Login successful.")

    # 2. Find TMF Contract (Micro TAIEX, Near Month)
    # Note: For backtest, we might want a specific contract passed as arg, 
    # but for simplicity we take the current near month TMF.
    print("Finding TMF (Micro TAIEX) contract...")
    # TMF is usually under Futures.TMF in Shioaji
    tmf_contracts = [
        c for c in trader.api.Contracts.Futures.TMF 
        if c.code[-2:] not in ["R1", "R2"]
        and c.delivery_date != "" # Filter out invalid if any
    ]
    
    if not tmf_contracts:
        print("No TMF contracts found.")
        return

    # Sort by delivery date to get the near month
    tmf_contracts.sort(key=lambda x: x.delivery_date)
    target_contract = tmf_contracts[0]
    print(f"Target Contract: {target_contract.name} ({target_contract.code})")

    # 3. Fetch Historical Data (1-minute bars)
    # kbars API: https://shioaji.github.io/shioaji/data/kbars/
    print("Fetching historical data (Last 180 days)...")
    now = datetime.now()
    start_date = (now - timedelta(days=180)).strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    
    # Shioaji kbars returns a specific object, convert to DataFrame
    # Note: Fetching 6 months of 1-minute data might be heavy or limited by API.
    # Future enhancement: Implement pagination or chunking if needed.
    kbars = trader.api.kbars(
        contract=target_contract, 
        start=start_date, 
        end=end_date
    )
    
    df_1m = pd.DataFrame({
        'ts': pd.to_datetime(kbars.ts),
        'open': kbars.Open,
        'high': kbars.High,
        'low': kbars.Low,
        'close': kbars.Close,
        'volume': kbars.Volume
    })
    
    if df_1m.empty:
        print("No historical data fetched.")
        return
        
    print(f"Fetched {len(df_1m)} 1-minute bars.")
    
    # Rename columns to standard lowercase
    df_1m.rename(columns={'ts': 'datetime'}, inplace=True)
    df_1m.set_index('datetime', inplace=True)
    
    # 4. Resample to 60m and 1D
    print("Resampling data...")
    ohlc_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }
    
    df_60m = df_1m.resample('60min', label='left', closed='left').apply(ohlc_dict).dropna()
    df_1d = df_1m.resample('1D', label='left', closed='left').apply(ohlc_dict).dropna()
    
    # Reset index to make datetime a column again for strategy access if needed
    df_60m.reset_index(inplace=True)
    df_1d.reset_index(inplace=True)
    
    print(f"60m Bars: {len(df_60m)}")
    print(f"1D Bars: {len(df_1d)}")
    
    # 4.5 Pre-calculate Indicators (O(N) Optimization)
    print("Pre-calculating indicators...")
    from src.strategies.indicators import calculate_supertrend, calculate_ut_bot, calculate_atr
    
    # 60m Trend
    # calculate_supertrend returns (is_uptrend, trend_line)
    # We need to apply it to the whole df_60m. 
    # Current implementation of calculate_supertrend returns the *last* value. 
    # We need to modify indicators.py or copy logic here to get the series.
    # Let's inspect indicators.py. 
    # It loops. We can just use the df returned if we modify it to return the df or use a new function.
    # Actually, calculate_supertrend in indicators.py returns `df['is_uptrend'].iloc[-1]`.
    # It DOES calculate the whole column 'is_uptrend' in the internal df.
    # We should refactor indicators.py to return the Series, or duplicate logic.
    # Refactoring indicators.py is cleaner.
    # But for now, let's just use the logic here to get the series.
    
    # Supertrend Logic (from indicators.py)
    def get_supertrend_series(df, period=10, multiplier=3.0):
        df = df.copy()
        atr = calculate_atr(df, period)
        hl2 = (df['high'] + df['low']) / 2
        df['upperband'] = hl2 + (multiplier * atr)
        df['lowerband'] = hl2 - (multiplier * atr)
        df['is_uptrend'] = True
        
        # Vectorized or loop? Supertrend is recursive, needs loop.
        # But we can optimize or just run it once.
        # Running it once for 1000 bars is fast (ms).
        # We need the 'is_uptrend' column.
        
        # Numba optimization or just basic loop
        close = df['close'].values
        upper = df['upperband'].values
        lower = df['lowerband'].values
        trend = np.ones(len(df), dtype=bool) # True = uptrend
        
        # Valid arrays
        if len(df) < period: return pd.Series([False]*len(df), index=df.index)

        # Naive loop for logic match
        for i in range(1, len(df)):
            if close[i] > upper[i-1]:
                trend[i] = True
            elif close[i] < lower[i-1]:
                trend[i] = False
            else:
                trend[i] = trend[i-1]
                
                if trend[i] and lower[i] < lower[i-1]:
                    lower[i] = lower[i-1]
                if not trend[i] and upper[i] > upper[i-1]:
                    upper[i] = upper[i-1]
        
        return pd.Series(trend, index=df.index)

    # UT Bot Logic (from indicators.py)
    def get_ut_bot_series(df, key_value=2, atr_period=10):
        df = df.copy()
        atr = calculate_atr(df, atr_period)
        ema_stop = np.zeros(len(df))
        close = df['close'].values
        atr_vals = atr.values
        
        signal = np.array(["None"] * len(df), dtype=object)
        
        # Loop
        for i in range(1, len(df)):
            src = close[i]
            loss = key_value * atr_vals[i]
            prev_stop = ema_stop[i-1]
            
            if src > prev_stop and close[i-1] > prev_stop:
                new_stop = max(prev_stop, src - loss)
            elif src < prev_stop and close[i-1] < prev_stop:
                new_stop = min(prev_stop, src + loss)
            else:
                new_stop = src - loss if src > prev_stop else src + loss
            ema_stop[i] = new_stop
            
        # Generate Signals
        # Signal logic: 
        # Buy: close > stop and prev_close <= prev_stop
        # Sell: close < stop and prev_close >= prev_stop
        
        current_stops = ema_stop
        prev_stops = np.roll(ema_stop, 1)
        prev_closes = np.roll(close, 1)
        
        buy_cond = (close > current_stops) & (prev_closes <= prev_stops)
        sell_cond = (close < current_stops) & (prev_closes >= prev_stops)
        
        signal[buy_cond] = "Buy"
        signal[sell_cond] = "Sell"
        
        return pd.Series(signal, index=df.index)

    # Calculate
    st_series = get_supertrend_series(df_1d)
    df_1d['is_uptrend'] = st_series
    
    ut_series = get_ut_bot_series(df_60m, key_value=3.5) # Optimized Parameter
    df_60m['signal'] = ut_series
    
    # Pre-calc ATR for 60m
    df_60m['atr'] = calculate_atr(df_60m)

    # 5. Simulation Loop
    print("Running simulation...")
    strategy = DualTimeframeStrategy(name="Gatekeeper-MXF-V1_Backtest")
    # from src.strategies.rubber_band import RubberBandStrategy
    # strategy = RubberBandStrategy(name="RubberBand_V1_Backtest")
    
    # Pre-calculate 1d indices
    times_1d = df_1d['datetime'].values
    
    print(f"Total steps: {len(df_60m)}")
    
    for i in range(len(df_60m)):
        if i % 1000 == 0:
            print(f"Step {i}/{len(df_60m)}...", end='\r')
            
        # Get pre-calculated values
        # Signal 60m
        sig_60m = df_60m['signal'].iloc[i]
        
        # Find 1d index
        current_60m_bar_time = df_60m.iloc[i]['datetime']
        
        # Type compatibility check not needed if we ensure both are datetime64 or Timestamp.
        # df_60m['datetime'] and df_1d['datetime'] came from resample, likely timestamps.
        # numpy array might be datetime64[ns].
        
        if isinstance(current_60m_bar_time, pd.Timestamp):
             target_time = current_60m_bar_time.to_datetime64()
        else:
             target_time = current_60m_bar_time

        idx = np.searchsorted(times_1d, target_time, side='left')
        
        if idx == 0:
            is_bull_1d = False # Default or skip
        else:
            # We want the status of the *completed* 60m bar relevant to now.
            # If current time is 10:05. idx points to 10:00 (starts at 10:00).
            # We want bar 09:00 (ends 10:00).
            # If idx points to 10:00, previous index is 09:00.
            # searchsorted('left'): returns i such that a[i-1] < v <= a[i].
            # If v=10:00 (exact match), it returns index of 10:00.
            # If v=10:05, it returns index of 11:00 (next one) if list is [09:00, 10:00, 11:00]?
            # No, if times_60m are start times.
            # 09:00, 10:00, 11:00.
            # target 10:05. 
            # 10:00 < 10:05 <= 11:00. Returns index of 11:00.
            # So idx-1 is 10:00.
            # But the 10:00 bar is NOT complete at 10:05.
            # So we need idx-2 (09:00, complete at 10:00).
            
            # Wait, 60m resample time is start time?
            # Shioaji kbars TS is start time. Resample 'left' usually keeps start time.
            # So 09:00 bar covers 09:00-10:00.
            # At 10:05, the 09:00 bar is complete.
            # The 10:00 bar (10:00-11:00) is developing.
            # Strategy checks "completed" trend?
            # Usually yes.
            # So we want the 09:00 bar.
            # If target is 10:05.
            # searchsorted([09:00, 10:00, 11:00], 10:05) -> returns index of 11:00.
            # idx-1 = 10:00.
            # idx-2 = 09:00.
            # So we need idx-2?
            
            # Let's verify what happens if target is 10:00 exactly.
            # searchsorted([..., 09:00, 10:00, 11:00], 10:00) -> returns index of 10:00.
            # idx-1 = 09:00.
            # At 10:00, the 09:00 bar (09:00-10:00) is Just Completed.
            # So we want idx-1.
            
            # So:
            # If target > times[idx-1] (e.g. 10:05 > 10:00), we actlually are in 10:00 bar (incomplete).
            # We want the one before 10:00 -> 09:00.
            # So if target > times[idx-1], we want idx-2.
            # If target == times[idx-1] (e.g. 10:00), we want idx-1 (09:00).
            
            # It seems robust to take:
            # The last bar that ENDED before or at target.
            # Bar 09 starts 09, ends 10.
            # If target 10:05. 09 ended (10) <= 10:05. Yes.
            # 10 starts 10, ends 11. 11 > 10:05. No.
            
            # Simplified:
            # We want row where (Start + 1h) <= CurrentTime.
            # Start <= CurrentTime - 1h.
            
            prev_1d = target_time - np.timedelta64(1440, 'm')
            idx_safe = np.searchsorted(times_1d, prev_1d, side='right') - 1
            
            if idx_safe < 0:
                is_bull_1d = False
            else:
                 is_bull_1d = df_1d['is_uptrend'].iloc[idx_safe]

        # Prepare inputs for DualTimeframeStrategy
        # Passing single-row DF for correctness with current DualLogic implementation
        df_60m_row = df_60m.iloc[[i]]
        df_1d_dummy = df_1d.iloc[[0]] 
        
        strategy.check_signals(
            df_60m_row, 
            df_1d_dummy, 
            precalc_bullish_1d=is_bull_1d, 
            precalc_signal_60m=sig_60m
        )
        
    print(f"\nSimulation complete.")
        
    # 6. Report
    print("-" * 50)
    print("Backtest Results")
    print("-" * 50)
    
    trades = strategy.trades
    total_trades = len(trades)
    
    if total_trades == 0:
        print("No trades generated.")
        return
        
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = (len(wins) / total_trades) * 100
    
    # Calculate Max Drawdown (Capital Curve)
    capital = 1000000 # Initial capital assumption
    equity_curve = [capital]
    current_equity = capital
    max_equity = capital
    max_dd = 0
    
    for t in trades:
        current_equity += t['pnl'] * 50 # Assuming 1 point = 50 TWD (Mini) or 200 (Large). MXF is 50? 
        # Micro is 50? Mxf is Micro Taiex, 1 pt = 10 NTD? No, Mini is 50, Micro is 10?
        # Let's check contract category. MXF (Micro) is 10 TWD per point? 
        # Or MTX (Mini) is 50. 
        # Spec: Micro Taiex Futures (MXF) -> 10 TWD / point?
        # User prompt mentioned "Maker 5m / 60m", "DualTimeframeStrategy".
        # Let's assume PnL in points for now in the summary.
        
        equity_curve.append(current_equity)
        max_equity = max(max_equity, current_equity)
        dd = max_equity - current_equity
        max_dd = max(max_dd, dd)

    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.2f}% ({len(wins)} Wins / {len(losses)} Losses)")
    print(f"Total PnL (Points): {total_pnl:.2f}")
    print(f"Avg PnL per Trade: {total_pnl / total_trades:.2f}")
    
    print("\nTrade Details:")
    trade_df = pd.DataFrame(trades)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.max_rows', None)
    print(trade_df[['strategy', 'entry_time', 'exit_time', 'entry_price', 'exit_price', 'reason', 'pnl']])
    
    # Determine exit code
    sys.exit(0)

if __name__ == "__main__":
    main()
