import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL")
print(f"Connecting to DB...")
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

try:
    # 1. 將虛擬部位歸零 (強制讓系統認為目前空手)
    cursor.execute("""
        UPDATE virtual_positions 
        SET position = 0, average_cost = 0 
        WHERE strategy_name = 'Gatekeeper-BNF-B';
    """)
    print("✅ 已將 Gatekeeper-BNF-B 虛擬部位重置為 0 (空手)")

    # 2. 刪除剛才那一筆因為下單失敗而錯誤記錄的進場紀錄
    # 尋找尚未平倉的紀錄並刪除
    cursor.execute("""
        DELETE FROM trade_history 
        WHERE strategy_name = 'Gatekeeper-BNF-B' 
        AND exit_time IS NULL;
    """)
    print("✅ 已將未實現的交易紀錄移除")

    conn.commit()
    print("🎉 資料庫狀態已修復！重啟主程式後部位與券商庫存將同步。")
except Exception as e:
    conn.rollback()
    print(f"❌ 發生錯誤: {e}")
finally:
    cursor.close()
    conn.close()
