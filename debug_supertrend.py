import sys
import pandas as pd
from datetime import datetime, timedelta
pd.set_option('display.max_rows', None)

sys.path.append('.')
from src.processors.kline_maker import KLineMaker
from src.connection import Trader
from src.strategies.indicators import calculate_supertrend, calculate_atr

print("Initializing trader...")
trader = Trader()
trader.login()
print("Trader logged in.")

tmf_contracts = [
    c for c in trader.api.Contracts.Futures.TMF 
    if c.code[-2:] not in ["R1", "R2"]
]
contract = tmf_contracts[0]
print(f"Contract: {contract.code}")

maker_1d = KLineMaker(timeframe=1440)
end_date = datetime.now().strftime("%Y-%m-%d")
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

print(f"Fetching kbars from {start_date} to {end_date}...")
kbars = trader.api.kbars(contract=contract, start=start_date, end=end_date)
df_1m = pd.DataFrame({
    'datetime': pd.to_datetime(kbars.ts),
    'open': kbars.Open,
    'high': kbars.High,
    'low': kbars.Low,
    'close': kbars.Close,
    'volume': kbars.Volume
})
df_1m.set_index('datetime', inplace=True)
ohlc_dict = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
df_1d_hist = df_1m.resample('1D', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()

print("Calculating Supertrend...")
df_1d_hist['atr'] = calculate_atr(df_1d_hist, period=10)
is_bullish, supertrend_val = calculate_supertrend(df_1d_hist)

print(df_1d_hist)
print(f"1D: BULL ({is_bullish}) | Supertrend: {supertrend_val}")

print("Logging out...")
try:
    trader.api.logout()
except:
    pass
print("Done.")
