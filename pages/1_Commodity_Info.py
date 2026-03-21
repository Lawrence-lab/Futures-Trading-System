import streamlit as st
import pandas as pd
import datetime
import sys
import os

# 將專案根目錄加入 path，以便能 import src.connection
sys.path.append(os.path.abspath('.'))
from src.connection import Trader

st.set_page_config(page_title="商品資訊 - 台指期", layout="wide")
st.title("📊 商品資訊 - 台指期 (TXF)")

@st.cache_resource(ttl=3600)
def get_api():
    try:
        trader = Trader()
        trader.login()
        return trader.api
    except Exception as e:
        st.error(f"API 登入失敗: {e}")
        return None

# 快取獲取的 K 線資料，減少 API 呼叫 (設定 1 小時過期)
@st.cache_data(ttl=3600)
def fetch_and_calculate_ma():
    api = get_api()
    if not api: return None
    
    try:
        # 取得台指期連續月合約 (TXFR1)
        txf_contract = api.Contracts.Futures.TXF.TXFR1
        
        # 為了計算 240MA，抓取過去 400 天的資料以確保有 240 個交易日
        start_date = (datetime.date.today() - datetime.timedelta(days=400)).strftime("%Y-%m-%d")
        end_date = datetime.date.today().strftime("%Y-%m-%d")
        
        kbars = api.kbars(txf_contract, start=start_date, end=end_date)
        
        df = pd.DataFrame({**kbars})
        if df.empty:
            return None
            
        # 統一轉為小寫，避免 Shioaji 的欄位大小寫不一致導致 KeyError
        df.columns = [col.lower() for col in df.columns]
        
        df['ts'] = pd.to_datetime(df['ts'])
        df.set_index('ts', inplace=True)
        
        # 將 1 分鐘 K 線 resample 為日 K 線 (Daily)
        # 用 D 頻率合併，並移除沒有交易紀錄的日期 (如假日)
        daily_df = df.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        # 計算移動平均線 (20MA, 60MA, 240MA)
        daily_df['20MA'] = daily_df['close'].rolling(window=20).mean()
        daily_df['60MA'] = daily_df['close'].rolling(window=60).mean()
        daily_df['240MA'] = daily_df['close'].rolling(window=240).mean()
        
        # 將 1 分鐘 K 線 resample 為小時 K 線 (Hourly, 60min)
        hourly_df = df.resample('1h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        # 計算小時級別移動平均線
        hourly_df['20MA'] = hourly_df['close'].rolling(window=20).mean()
        hourly_df['60MA'] = hourly_df['close'].rolling(window=60).mean()
        hourly_df['240MA'] = hourly_df['close'].rolling(window=240).mean()
        
        return daily_df.iloc[-1], hourly_df.iloc[-1]
    except Exception as e:
        st.error(f"抓取資料或計算均線時發生錯誤: {e}")
        return None

with st.spinner('正在載入歷史 K 線與計算指標中... (這可能需要幾秒鐘)'):
    result = fetch_and_calculate_ma()

if result is not None:
    latest_daily, latest_hourly = result
    
    current_price = latest_daily['close']
    
    # Daily MAs
    d_ma20 = latest_daily['20MA']
    d_ma60 = latest_daily['60MA']
    d_ma240 = latest_daily['240MA']
    
    # Hourly MAs
    h_ma20 = latest_hourly['20MA']
    h_ma60 = latest_hourly['60MA']
    h_ma240 = latest_hourly['240MA']
    
    st.subheader(f"最新收盤價: {current_price:,.0f}")
    
    # 計算乖離率 Bias = (Price - MA) / MA * 100
    def calc_bias(price, ma):
        if pd.isna(ma) or ma == 0: return "N/A"
        return f"{(price - ma) / ma * 100:.2f}%"
        
    def format_ma(ma):
        if pd.isna(ma): return "資料不足"
        return f"{ma:,.0f}"

    st.markdown("### 📈 日線級別 (Daily)")
    col1, col2, col3 = st.columns(3)
    col1.metric("月線 (20MA)", format_ma(d_ma20), calc_bias(current_price, d_ma20))
    col2.metric("季線 (60MA)", format_ma(d_ma60), calc_bias(current_price, d_ma60))
    col3.metric("年線 (240MA)", format_ma(d_ma240), calc_bias(current_price, d_ma240))
    
    st.markdown("### 📉 小時線級別 (Hourly)")
    col4, col5, col6 = st.columns(3)
    col4.metric("20MA (近一日)", format_ma(h_ma20), calc_bias(current_price, h_ma20))
    col5.metric("60MA (近三日)", format_ma(h_ma60), calc_bias(current_price, h_ma60))
    col6.metric("240MA (近半月)", format_ma(h_ma240), calc_bias(current_price, h_ma240))
    
    st.markdown("---")
    st.info("💡 **說明**：\n- 這邊抓取的是台指期近月連續合約(TXFR1)。\n- 乖離率為正 (綠色/紅色) 表示目前價格在均線上；負值表示在均線下。若數值旁有紅色箭頭向下為跌破，綠色向上為突破。")
else:
    st.warning("目前無法載入資料，請稍後再重試或檢查 API 狀態。")
