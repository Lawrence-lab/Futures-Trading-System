import sys
import os
sys.path.append(os.path.abspath('.'))
from src.connection import Trader

def main():
    trader = Trader()
    trader.login()
    print("Contracts attributes:")
    print([attr for attr in dir(trader.api.Contracts) if not attr.startswith('_')])
    
    if hasattr(trader.api.Contracts, 'Futures'):
        print("\nFutures attributes:")
        print([attr for attr in dir(trader.api.Contracts.Futures) if not attr.startswith('_')])

    if hasattr(trader.api.Contracts, 'OVS'):
        print("\nOVS attributes:")
        print([attr for attr in dir(trader.api.Contracts.OVS) if not attr.startswith('_')])

    trader.api.logout()

if __name__ == '__main__':
    main()
