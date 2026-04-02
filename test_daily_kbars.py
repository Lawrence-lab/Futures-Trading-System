import sys
import os
sys.path.append(os.path.abspath('.'))
from src.connection import Trader
import pandas as pd
import datetime

def main():
    trader = Trader()
    trader.login()
    
    # Test TXF (Futures)
    try:
        txf_contract = trader.api.Contracts.Futures.TXF.TXFR1
        print(f"Fetching Kbars for {txf_contract.code}...")
        # Since we need 240 days, let's fetch 1 year
        start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
        kbars = trader.api.kbars(txf_contract, start=start_date, end=datetime.date.today().strftime("%Y-%m-%d"))
        df = pd.DataFrame({**kbars})
        df.ts = pd.to_datetime(df.ts)
        print(f"TXF Kbars rows: {len(df)}")
        if len(df) > 0:
            print(f"First ts: {df.ts.iloc[0]}, Last ts: {df.ts.iloc[-1]}")
            # check the interval
            diff = df.ts.iloc[1] - df.ts.iloc[0]
            print(f"TXF Interval: {diff}")
    except Exception as e:
        print(f"TXF Error: {e}")

    # Test TSE (Index)
    try:
        tse_contract = trader.api.Contracts.Indexs.TSE.TSE01
        print(f"\nFetching Kbars for {tse_contract.code}...")
        start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
        kbars = trader.api.kbars(tse_contract, start=start_date, end=datetime.date.today().strftime("%Y-%m-%d"))
        df = pd.DataFrame({**kbars})
        df.ts = pd.to_datetime(df.ts)
        print(f"TSE Kbars rows: {len(df)}")
        if len(df) > 0:
            print(f"First ts: {df.ts.iloc[0]}, Last ts: {df.ts.iloc[-1]}")
            diff = df.ts.iloc[1] - df.ts.iloc[0]
            print(f"TSE Interval: {diff}")
    except Exception as e:
        print(f"TSE Error: {e}")

    trader.api.logout()

if __name__ == "__main__":
    main()
