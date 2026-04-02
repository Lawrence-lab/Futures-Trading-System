import sys
import pandas as pd
from datetime import datetime, timedelta
sys.path.append('.')
from src.processors.kline_maker import KLineMaker
from src.connection import Trader
from src.strategies.indicators import calculate_supertrend, calculate_atr, calculate_ut_bot, calculate_adx, calculate_sma, calculate_bias

def run_analysis():
    trader = Trader()
    trader.login()
    
    # 1. Get correct target contract
    from datetime import datetime
    import pytz
    tw_tz = pytz.timezone('Asia/Taipei')
    now_tw = datetime.now(tw_tz)
    current_date_str = now_tw.strftime("%Y/%m/%d")
    current_hm_str = now_tw.strftime("%H:%M")

    tmf_contracts = [c for c in trader.api.Contracts.Futures.TMF if c.code[-2:] not in ["R1", "R2"]]
    valid_contracts = []
    for c in tmf_contracts:
        if hasattr(c, 'delivery_date') and getattr(c, 'delivery_date'):
            if c.delivery_date < current_date_str:
                continue
            if c.delivery_date == current_date_str and current_hm_str >= "13:30":
                continue
        valid_contracts.append(c)
    
    valid_contracts.sort(key=lambda x: getattr(x, 'delivery_date', '9999/99/99'))
    contract = valid_contracts[0]
    print(f"Contract: {contract.code} {contract.symbol}")
    
    # Fetch data
    end_date = now_tw.strftime("%Y-%m-%d")
    start_date = (now_tw - timedelta(days=30)).strftime("%Y-%m-%d")
    print(f"Fetching data from {start_date} to {end_date}...")
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
    
    df_5m = df_1m.resample('5min', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
    df_60m = df_1m.resample('60min', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
    df_1d = df_1m.resample('1D', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
    
    print("\n--- 1D Trend ---")
    df_1d['atr'] = calculate_atr(df_1d, period=10)
    is_bullish, supertrend_val = calculate_supertrend(df_1d)
    trend = "BULL (多)" if is_bullish else "BEAR (空)"
    print(f"Current Trend: {trend}")
    print(f"Recent 1D Close: {df_1d.iloc[-1]['close']} | Supertrend: {supertrend_val}")
    
    print("\n--- Strategy 1: Gatekeeper-MXF-V1 (DualTimeframe) ---")
    df_60m['atr'] = calculate_atr(df_60m, period=10)
    adx_series = calculate_adx(df_60m, period=14)
    df_60m['adx'] = adx_series
    signal_60m = calculate_ut_bot(df_60m, key_value=3.5)
    last_60m = df_60m.iloc[-1]
    print(f"60M Signal (UT Bot): {signal_60m}")
    print(f"60M ADX (Need > 25.0): {last_60m['adx']:.2f}")
    if is_bullish and signal_60m == "Buy" and last_60m['adx'] > 25.0:
        print(">>> OPPORTUNITY: LONG Signal Active on 60M!")
    elif not is_bullish and signal_60m == "Sell" and last_60m['adx'] > 25.0:
        print(">>> OPPORTUNITY: SHORT Signal Active on 60M!")
    else:
        print(">>> No immediate signal on 60M DualTimeframe.")
        
    print("\n--- Strategy 2: Gatekeeper-BNF-B (5M Reversion) ---")
    sma_series = calculate_sma(df_5m, period=60)
    bias_series = calculate_bias(df_5m, sma_col=None, period=60)
    vol_ma_series = df_5m['volume'].rolling(window=20).mean()
    last_5m = df_5m.iloc[-1]
    last_bias = bias_series.iloc[-1]
    last_vol = last_5m['volume']
    last_vol_ma = vol_ma_series.iloc[-1]
    print(f"5M 60MA Bias (Need < -1.5% for long, > 1.5% for short): {last_bias:.3f}%")
    print(f"5M Volume: {last_vol} | 20MA Volume: {last_vol_ma:.1f} (Need > {last_vol_ma*2:.1f})")
    
    if is_bullish and last_bias < -1.5 and last_vol > last_vol_ma * 2:
        print(">>> OPPORTUNITY: LONG Signal (Bottom Fishing) Active on 5M!")
    elif not is_bullish and last_bias > 1.5 and last_vol > last_vol_ma * 2:
        print(">>> OPPORTUNITY: SHORT Signal (Top Fishing) Active on 5M!")
    else:
        dist_to_long = (last_bias - -1.5) if is_bullish else None
        dist_to_short = (1.5 - last_bias) if not is_bullish else None
        print(f">>> No immediate signal on 5M. ", end="")
        if dist_to_long is not None and dist_to_long > 0:
            print(f"Need bias to drop {dist_to_long:.2f}% further to hit -1.5%.")
        elif dist_to_short is not None and dist_to_short > 0:
            print(f"Need bias to rise {dist_to_short:.2f}% further to hit +1.5%.")
        else:
            print("Bias is close, waiting for volume spike.")

    trader.api.logout()

if __name__ == "__main__":
    run_analysis()
