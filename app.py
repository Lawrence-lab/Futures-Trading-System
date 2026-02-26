import streamlit as st
import pandas as pd
from src.db_logger import get_streamlit_db_connection

st.set_page_config(page_title="交易追蹤儀表板", layout="wide")
st.title("📈 演算法交易追蹤儀表板")

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
    
    # 2. 權益總額 (最新的一筆 equity_logs)
    cursor.execute("""
        SELECT total_equity, available_margin, log_date
        FROM equity_logs
        ORDER BY log_date DESC
        LIMIT 1;
    """)
    latest_equity = cursor.fetchone()
    
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
    eq_val = f"{latest_equity[0]:,.0f}" if latest_equity and latest_equity[0] is not None else "N/A"
    col2.metric("💰 權益總額", eq_val)
    
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
    st.dataframe(df_trades, use_container_width=True)
    
except Exception as e:
    st.error(f"讀取資料庫時發生錯誤：{e}")

# 備註：在 Streamlit 使用 st.cache_resource 快取的資料庫連線，不需要也不可以呼叫 conn.close()。
