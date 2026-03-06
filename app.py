import streamlit as st
import pandas as pd
import warnings
from src.db_logger import get_streamlit_db_connection

# Suppress Pandas SQLAlchemy warning since we use direct psycopg2 connection here
warnings.filterwarnings('ignore', message='.*pandas only supports SQLAlchemy connectable.*')

st.set_page_config(page_title="交易追蹤儀表板", layout="wide")
st.title("📈 演算法交易追蹤儀表板")

@st.cache_resource(ttl=3600) # Cache the Shioaji API instance, but refresh every hour to avoid token expiration
def get_shioaji_api():
    from src.connection import Trader
    try:
        trader = Trader()
        trader.login()
        return trader.api
    except Exception as e:
        st.error(f"Shioaji API 登入失敗: {e}")
        return None

def get_realtime_equity(api):
    if not api: return None
    try:
        acc = api.futopt_account
        if acc:
            margin_res = api.margin(acc)
            if margin_res:
                margin_data = margin_res[0] if isinstance(margin_res, list) and len(margin_res) > 0 else margin_res
                t_equity = getattr(margin_data, 'equity', 0.0) 
                if not t_equity and isinstance(margin_data, dict):
                    t_equity = margin_data.get('equity', 0.0)
                return float(t_equity)
    except Exception as e:
        print(f"取得即時權益數失敗: {e}")
    return None

api = get_shioaji_api()
realtime_equity = get_realtime_equity(api)

conn = get_streamlit_db_connection()
if not conn:
    st.error("無法連線至資料庫，請檢查連線設定與網絡狀態。")
    st.stop()

# 根據要求讀取資料庫
try:
    cursor = conn.cursor()
    
    # 1. 當前倉位 (最後一筆 status 為 Open 的紀錄)
    cursor.execute("""
        SELECT side, entry_price, entry_time
        FROM trade_history
        WHERE status = 'Open'
        ORDER BY entry_time DESC
        LIMIT 1;
    """)
    current_position = cursor.fetchone()
    
    # 2. 權益總額 (從資料庫當作備用 fallback)
    cursor.execute("""
        SELECT total_equity, available_margin, log_date
        FROM equity_logs
        ORDER BY log_date DESC
        LIMIT 1;
    """)
    latest_equity_db = cursor.fetchone()
    
    # 3. 本週點數損益 (近 7 天)
    cursor.execute("""
        SELECT SUM(pnl_points)
        FROM trade_history
        WHERE status = 'Closed' 
          AND exit_time >= CURRENT_DATE - INTERVAL '7 days';
    """)
    weekly_pnl = cursor.fetchone()[0]
    
    cursor.close()
    
    # --- 顯示數據列 ---
    col1, col2, col3 = st.columns(3)
    
    # 當前倉位處理
    if current_position:
        side = "做多 (Buy)" if current_position[0] == "Buy" else "做空 (Sell)"
        price = f"{current_position[1]:.1f}"
        pos_text = f"{side} @ {price}"
    else:
        pos_text = "目前空手"
        
    col1.metric("📌 當前倉位", pos_text)
    
    # 權益總額處理
    if realtime_equity is not None:
        eq_val = f"{realtime_equity:,.0f}"
    else:
        eq_val = f"{latest_equity_db[0]:,.0f}" if latest_equity_db and latest_equity_db[0] is not None else "N/A"
        
    col2.metric("💰 即時權益總額", eq_val)
    
    # 本週點數損益處理
    pnl_val = f"{weekly_pnl:+.1f} 點" if weekly_pnl is not None else "0 點"
    col3.metric("📅 本週已實現損益", pnl_val)
    
    st.markdown("---")
    
    # --- 顯示詳細資料表 ---
    st.subheader("📋 歷史交易紀錄 (近 50 筆)")
    df_trades = pd.read_sql("""
        SELECT id, strategy_name, side, entry_price, entry_time, exit_price, exit_time, pnl_points, status
        FROM trade_history
        ORDER BY id DESC
        LIMIT 50;
    """, conn)
    st.dataframe(df_trades, width="stretch")
    
except Exception as e:
    st.error(f"讀取資料庫時發生錯誤：{e}")

# 備註：在 Streamlit 使用 st.cache_resource 快取的資料庫連線，不需要也不可以呼叫 conn.close()。
