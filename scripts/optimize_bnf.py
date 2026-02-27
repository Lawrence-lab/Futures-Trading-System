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
from src.strategies.gatekeeper_bnf_b import GatekeeperBNFBStrategy
from src.portfolio_manager import PortfolioManager
from src.strategies.indicators import calculate_atr

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
    
    return df_60m, df_1d

def run_simulation(df_60m, df_1d, bias, vol_ratio):
    # Dummy Portfolio to silence errors
    strategy = GatekeeperBNFBStrategy(name="Gatekeeper-BNF-B_Opt", portfolio=None, contract=None)
    
    # 覆寫欲測試的參數
    strategy.bias_threshold = bias
    strategy.volume_spike_ratio = vol_ratio
    # 其他可以固定的參數: strategy.fixed_sl_points = 100 等
    
    df_1d_dummy = df_1d.iloc[[0]] if not df_1d.empty else None
    
    for i in range(len(df_60m)):
        df_60m_window = df_60m.iloc[max(0, i-100):i+1]
        strategy.check_signals(df_60m_window, df_1d_dummy)
            
    trades = strategy.trades
    total_trades = len(trades)
    if total_trades == 0:
        return 0, 0, 0
        
    wins = [t for t in trades if t['pnl'] > 0]
    total_pnl = sum(t['pnl'] for t in trades)
    win_rate = (len(wins) / total_trades) * 100
    
    return total_trades, win_rate, total_pnl

def main():
    print("Initializing Parameter Optimization...")
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
    # Bias 從 -1.0% 到 -3.0%，間隔 0.5%
    bias_range = [-1.0, -1.5, -2.0, -2.5, -3.0]
    
    # 成交量爆量倍數 從 1.2倍 到 2.0倍
    vol_ratio_range = [1.2, 1.5, 1.8, 2.0]
    
    results = []
    total_combinations = len(bias_range) * len(vol_ratio_range)
    current_idx = 1
    
    print("-" * 60)
    print(f"{'Bias %':>8} | {'Vol Ratio':>10} | {'Trades':>8} | {'Win Rate %':>12} | {'Total PnL':>10}")
    print("-" * 60)

    for bias, vol in itertools.product(bias_range, vol_ratio_range):
        # 顯示進度
        sys.stdout.write(f"\rEvaluating {current_idx}/{total_combinations}...")
        sys.stdout.flush()
        
        trades_count, win_rate, pnl = run_simulation(df_60m, df_1d, bias, vol)
        
        # 儲存結果
        results.append({
            'Bias': bias,
            'Vol_Ratio': vol,
            'Trades': trades_count,
            'Win_Rate': win_rate,
            'PnL': pnl
        })
        current_idx += 1
        
    print("\n" + "-" * 60)
    
    # 將結果轉為 DataFrame 排序
    res_df = pd.DataFrame(results)
    # 根據 PnL 降冪排序，只顯示最好的一批
    res_df = res_df.sort_values(by='PnL', ascending=False).reset_index(drop=True)
    
    for idx, row in res_df.iterrows():
        print(f"{row['Bias']:>8.1f} | {row['Vol_Ratio']:>10.1f} | {int(row['Trades']):>8d} | {row['Win_Rate']:>11.2f}% | {row['PnL']:>10.1f}")

    best_setup = res_df.iloc[0]
    print("-" * 60)
    print(f"🏆 Best Combination Setup: Bias {best_setup['Bias']}%, Volume Ratio {best_setup['Vol_Ratio']}x")
    print(f"=> Expected PnL: {best_setup['PnL']}, Trades: {int(best_setup['Trades'])}")

if __name__ == "__main__":
    main()
