import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("❌ ERROR: DATABASE_URL is not set.")
    exit(1)

# SQL Statements
create_trade_history_sql = """
CREATE TABLE IF NOT EXISTS trade_history (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(50) DEFAULT 'Gatekeeper_V1',
    side VARCHAR(10),        -- 'Buy' 或 'Sell'
    entry_price NUMERIC,     -- 進場價
    entry_time TIMESTAMP,    -- 進場時間
    exit_price NUMERIC,      -- 出場價
    exit_time TIMESTAMP,     -- 出場時間
    pnl_points NUMERIC,      -- 損益點數
    status VARCHAR(20)       -- 'Open' 或 'Closed'
);
"""

create_equity_logs_sql = """
CREATE TABLE IF NOT EXISTS equity_logs (
    id SERIAL PRIMARY KEY,
    log_date DATE UNIQUE,    -- 日期
    total_equity NUMERIC,    -- 總權益數
    available_margin NUMERIC -- 可用保證金
);
"""

try:
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    print("正在建立 trade_history 表格...")
    cursor.execute(create_trade_history_sql)
    
    print("正在建立 equity_logs 表格...")
    cursor.execute(create_equity_logs_sql)
    
    conn.commit()
    print("✅ 表格建立成功！")
    
    cursor.close()
    conn.close()
except psycopg2.Error as e:
    print(f"❌ 資料庫錯誤: {e}")
except Exception as e:
    print(f"❌ 發生錯誤: {e}")
