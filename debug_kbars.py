import sys
import os
sys.path.append(os.path.abspath('.'))
from src.connection import Trader
import pandas as pd
import datetime

def main():
    trader = Trader()
    trader.login()
    txf_contract = trader.api.Contracts.Futures.TXF.TXFR1
    start_date = (datetime.date.today() - datetime.timedelta(days=5)).strftime("%Y-%m-%d")
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    
    kbars = trader.api.kbars(txf_contract, start=start_date, end=end_date)
    df = pd.DataFrame({**kbars})
    print("Columns:", df.columns.tolist())
    trader.api.logout()

if __name__ == "__main__":
    main()
