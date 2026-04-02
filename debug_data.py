import sys
import pandas as pd
from datetime import datetime, timedelta
sys.path.append('.')
from src.processors.kline_maker import KLineMaker
from src.connection import Trader

trader = Trader()
trader.login()
tmf_contracts = [
    c for c in trader.api.Contracts.Futures.TMF 
    if c.code[-2:] not in ["R1", "R2"]
]
contract = tmf_contracts[0]

maker_1d = KLineMaker(timeframe=1440)
end_date = datetime.now().strftime("%Y-%m-%d")
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

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

# check for zeroes or massive drops
print("Total 1m bars:", len(df_1m))
print("Zeroes in high:", (df_1m['high'] == 0).sum())
print("Zeroes in low:", (df_1m['low'] == 0).sum())
print("Zeroes in close:", (df_1m['close'] == 0).sum())

ohlc_dict = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
df_1d_hist = df_1m.resample('1D', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()

from src.strategies.indicators import calculate_supertrend, calculate_atr
df_1d_hist['atr'] = calculate_atr(df_1d_hist, period=10)
print(df_1d_hist[['datetime', 'high', 'low', 'close', 'atr']])
is_bullish, supertrend_val = calculate_supertrend(df_1d_hist)
print(f"1D: BULL ({is_bullish}) | Supertrend: {supertrend_val}")

trader.api.logout()
