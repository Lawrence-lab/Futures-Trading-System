import sys
import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.connection import Trader
from src.strategies.gatekeeper_bnf_b import GatekeeperBNFBStrategy
from src.strategies.gatekeeper_bnf_b_5m import GatekeeperBNFB5mStrategy
import logging

os.environ["DISABLE_LINE_NOTIFY"] = "true"
os.environ["SIMULATION"] = "True"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_data_in_chunks(api, contract, days_total=180, chunk_days=30):
    kbars_list = []
    end = datetime.now()
    
    chunks = []
    current_end = end
    for _ in range(0, days_total, chunk_days):
        current_start = current_end - timedelta(days=chunk_days)
        chunks.append((current_start.strftime('%Y-%m-%d'), current_end.strftime('%Y-%m-%d')))
        current_end = current_start
        
    chunks.reverse() # Oldest to newest
    
    for start_date, end_date in chunks:
        print(f"Fetching from {start_date} to {end_date}...")
        kbars = api.kbars(contract=contract, start=start_date, end=end_date)
        if kbars.ts:
            df = pd.DataFrame({
                'datetime': pd.to_datetime(kbars.ts),
                'open': kbars.Open,
                'high': kbars.High,
                'low': kbars.Low,
                'close': kbars.Close,
                'volume': kbars.Volume
            })
            kbars_list.append(df)
            
    if not kbars_list:
        return pd.DataFrame()
        
    df_1m = pd.concat(kbars_list).drop_duplicates(subset=['datetime']).sort_values('datetime')
    df_1m.set_index('datetime', inplace=True)
    return df_1m

def get_supertrend_series(df, period=10, multiplier=3.0):
    from src.strategies.indicators import calculate_atr
    df = df.copy()
    atr = calculate_atr(df, period)
    hl2 = (df['high'] + df['low']) / 2
    df['upperband'] = hl2 + (multiplier * atr)
    df['lowerband'] = hl2 - (multiplier * atr)
    df['is_uptrend'] = True
    
    close = df['close'].values
    upper = df['upperband'].values
    lower = df['lowerband'].values
    trend = np.ones(len(df), dtype=bool) 
    
    if len(df) < period: return pd.Series([False]*len(df), index=df.index)

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

def main():
    print("Initializing Backtest Comparison (6 Months)...")
    trader = Trader()
    trader.login()
    
    tmf_contracts = [c for c in trader.api.Contracts.Futures.TMF if c.code[-2:] not in ["R1", "R2"] and c.delivery_date != ""]
    if not tmf_contracts:
        print("No TMF contracts found.")
        sys.exit(1)
        
    tmf_contracts.sort(key=lambda x: x.delivery_date)
    target_contract = tmf_contracts[0]
    print(f"Target Contract: {target_contract.name} ({target_contract.code})")

    df_1m = fetch_data_in_chunks(trader.api, target_contract, days_total=180, chunk_days=30)
    
    if df_1m.empty:
        print("No historical data fetched.")
        sys.exit(1)
        
    print(f"Fetched {len(df_1m)} 1-minute bars.")
    
    print("Resampling data...")
    ohlc_dict = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
    
    df_5m = df_1m.resample('5min', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
    df_60m = df_1m.resample('60min', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
    df_1d = df_1m.resample('1D', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
    
    print(f"5m Bars: {len(df_5m)}, 60m Bars: {len(df_60m)}, 1D Bars: {len(df_1d)}")
    
    st_series = get_supertrend_series(df_1d)
    df_1d['is_uptrend'] = st_series
    
    print("Running simulation...")
    
    strategies = [
        GatekeeperBNFBStrategy(name="Gatekeeper-BNF-B_60m_Backtest", portfolio=None, contract=target_contract),
        GatekeeperBNFB5mStrategy(name="Gatekeeper-BNF-B_5m_Backtest", portfolio=None, contract=target_contract)
    ]
    
    # Run 60m strategy loop
    print("Running 60m strategy simulation...")
    times_1d = df_1d['datetime'].values
    for i in range(len(df_60m)):
        current_60m_bar_time = df_60m.iloc[i]['datetime']
        target_time = current_60m_bar_time.to_datetime64() if isinstance(current_60m_bar_time, pd.Timestamp) else current_60m_bar_time
        prev_1d = target_time - np.timedelta64(1440, 'm')
        idx_safe = np.searchsorted(times_1d, prev_1d, side='right') - 1
        is_bull_1d = df_1d['is_uptrend'].iloc[idx_safe] if idx_safe >= 0 else False
        
        df_60m_window = df_60m.iloc[max(0, i-100):i+1]
        df_1d_dummy = df_1d.iloc[[0]] 
        
        strategies[0].check_signals(df_60m_window, df_1d_dummy, precalc_bullish_1d=is_bull_1d)

    # Run 5m strategy loop
    print("Running 5m strategy simulation...")
    for i in range(len(df_5m)):
        if i % 5000 == 0:
            print(f"Step {i}/{len(df_5m)}...")
        current_5m_bar_time = df_5m.iloc[i]['datetime']
        target_time = current_5m_bar_time.to_datetime64() if isinstance(current_5m_bar_time, pd.Timestamp) else current_5m_bar_time
        prev_1d = target_time - np.timedelta64(1440, 'm')
        idx_safe = np.searchsorted(times_1d, prev_1d, side='right') - 1
        is_bull_1d = df_1d['is_uptrend'].iloc[idx_safe] if idx_safe >= 0 else False
        
        df_5m_window = df_5m.iloc[max(0, i-100):i+1]
        df_1d_dummy = df_1d.iloc[[0]] 
        
        strategies[1].check_signals(df_5m_window, df_1d_dummy, precalc_bullish_1d=is_bull_1d)

    print(f"\nSimulation complete.")
        
    print("-" * 50)
    print("Backtest Results Comparison (6 Months)")
    print("-" * 50)
    
    for strategy in strategies:
        trades = strategy.trades
        total_trades = len(trades)
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in trades)
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
        
        print(f"\n=== {strategy.name} ===")
        print(f"Total Trades: {total_trades}")
        print(f"Win Rate: {win_rate:.2f}% ({len(wins)} Wins / {len(losses)} Losses)")
        print(f"Total PnL (Points): {total_pnl:.2f}")
        print(f"Avg PnL per Trade: {(total_pnl / total_trades) if total_trades > 0 else 0:.2f}")
    
    print("\nDetailed Trades:")
    trades_all = strategies[0].trades + strategies[1].trades
    if trades_all:
        trade_df = pd.DataFrame(trades_all)
        trade_df = trade_df.sort_values('entry_time')
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        pd.set_option('display.max_rows', None)
        print(trade_df[['strategy', 'entry_time', 'exit_time', 'entry_price', 'exit_price', 'reason', 'pnl']])

if __name__ == "__main__":
    main()
