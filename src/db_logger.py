import os
import psycopg2
from dotenv import load_dotenv
import logging

load_dotenv()

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logging.error("❌ ERROR: DATABASE_URL is not set.")
        return None
    try:
        return psycopg2.connect(db_url)
    except Exception as e:
        logging.error(f"❌ Database connection failed: {e}")
        return None

def log_trade_entry(strategy_name: str, side: str, entry_price: float, entry_time) -> int:
    """Logs the entry of a trade to the trade_history table and returns the inserted ID."""
    conn = get_db_connection()
    if not conn: return -1
    
    trade_id = -1
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO trade_history (strategy_name, side, entry_price, entry_time, status)
            VALUES (%s, %s, %s, %s, 'Open')
            RETURNING id;
            """,
            (strategy_name, side, entry_price, entry_time)
        )
        trade_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
    except Exception as e:
        logging.error(f"Failed to log trade entry to DB: {e}")
    finally:
        conn.close()
    return trade_id

def log_trade_exit(trade_id: int, exit_price: float, exit_time, pnl_points: float):
    """Updates an existing trade record with exit information."""
    if trade_id == -1: return
    
    conn = get_db_connection()
    if not conn: return
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE trade_history 
            SET exit_price = %s, exit_time = %s, pnl_points = %s, status = 'Closed'
            WHERE id = %s;
            """,
            (exit_price, exit_time, pnl_points, trade_id)
        )
        conn.commit()
        cursor.close()
    except Exception as e:
        logging.error(f"Failed to log trade exit to DB: {e}")
    finally:
        conn.close()

def log_daily_equity(log_date, total_equity: float, available_margin: float):
    """Logs daily equity to the equity_logs table."""
    conn = get_db_connection()
    if not conn: return
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO equity_logs (log_date, total_equity, available_margin)
            VALUES (%s, %s, %s)
            ON CONFLICT (log_date) 
            DO UPDATE SET total_equity = EXCLUDED.total_equity, available_margin = EXCLUDED.available_margin;
            """,
            (log_date, total_equity, available_margin)
        )
        conn.commit()
        cursor.close()
    except Exception as e:
        logging.error(f"Failed to log daily equity to DB: {e}")
    finally:
        conn.close()

# --- Streamlit 專用連線 ---
# 因為 Streamlit 每次互動都會重新執行腳本，我們利用 @st.cache_resource
# 來快取資料庫連線，避免頻繁斷開與重新連線造成資料庫負載過高。
try:
    import streamlit as st

    @st.cache_resource(ttl=3600) # 快取有效時間設定 (例如 1 小時)
    def get_streamlit_db_connection():
        """
        取得供 Streamlit 儀表板使用的快取 PostgreSQL 連線。
        (請勿在背景任務中使用此連線，且避免手動 conn.close())
        """
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            st.error("❌ DATABASE_URL is not set.")
            return None
            
        try:
            return psycopg2.connect(db_url)
        except Exception as e:
            st.error(f"❌ Streamlit DB Connection failed: {e}")
            return None
            
except ImportError:
    # 執行主程式時如果沒有 import streamlit 也不會報錯
    pass
