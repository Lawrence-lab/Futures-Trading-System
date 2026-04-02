import time
import sys
import os
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
    if not tmf_contracts:
        print("No TMF contracts found.")
        sys.exit()
    contract = tmf_contracts[0]
    print(f"Contract: {contract}")
    
    def on_tick(exchange, tick):
        print(f"Tick received: {tick}")
        
    trader.api.quote.set_on_tick_fop_v1_callback(on_tick)
    trader.api.quote.subscribe(contract, quote_type=sj.constant.QuoteType.Tick)
    
    print("Waiting 10 seconds for ticks...")
    time.sleep(10)
    trader.api.logout()

if __name__ == '__main__':
    main()
