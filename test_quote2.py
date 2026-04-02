import time
import sys
import os
from datetime import datetime
import pytz
sys.path.append(os.path.abspath('.'))
from src.connection import Trader
import shioaji as sj

def main():
    trader = Trader()
    trader.login()
    
    tmf_contracts = [
        c for c in trader.api.Contracts.Futures.TMF 
        if c.code[-2:] not in ["R1", "R2"]
    ]
    
    tw_tz = pytz.timezone('Asia/Taipei')
    now_tw = datetime.now(tw_tz)
    current_date_str = now_tw.strftime("%Y/%m/%d")
    current_hm_str = now_tw.strftime("%H:%M")

    valid_contracts = []
    for c in tmf_contracts:
        if hasattr(c, 'delivery_date') and getattr(c, 'delivery_date'):
            if c.delivery_date < current_date_str:
                continue
            if c.delivery_date == current_date_str and current_hm_str >= "13:30":
                continue
        valid_contracts.append(c)

    if not valid_contracts:
        print("找不到有效的 TMF 合約。")
        sys.exit(1)
        
    valid_contracts.sort(key=lambda x: getattr(x, 'delivery_date', '9999/99/99'))
    contract = valid_contracts[0]
    print(f"Correct night session Contract: {contract}")
    
    def on_tick(exchange, tick):
        print(f"Tick received: {tick}")
        
    trader.api.quote.set_on_tick_fop_v1_callback(on_tick)
    trader.api.quote.set_on_bidask_fop_v1_callback(on_tick)
    trader.api.quote.subscribe(contract, quote_type=sj.constant.QuoteType.Tick)
    trader.api.quote.subscribe(contract, quote_type=sj.constant.QuoteType.BidAsk)
    
    print("Waiting 10 seconds for ticks...")
    time.sleep(10)
    trader.api.logout()

if __name__ == '__main__':
    main()
