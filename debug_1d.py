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
print(f"Contract: {contract}")

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
ohlc_dict = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
df_1d_hist = df_1m.resample('1D', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
maker_1d.load_historical_dataframe(df_1d_hist)

df_1d = maker_1d.get_dataframe()
print(f"df_1d length: {len(df_1d)}")
if not df_1d.empty and len(df_1d) >= 10:
    from src.strategies.indicators import calculate_supertrend
    try:
        is_bullish, supertrend_val = calculate_supertrend(df_1d)
        print(f"1D: BULL ({is_bullish}) | Supertrend: {supertrend_val}")
    except Exception as e:
        print(f"calculate_supertrend explicitly threw: {e}")
        import traceback
        traceback.print_exc()
else:
    print("DataFrame empty or < 10 rows")

trader.logout()
