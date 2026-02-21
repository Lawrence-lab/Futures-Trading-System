import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("❌ ERROR: DATABASE_URL is not set.")
    exit(1)

# Hide password part roughly for display
masked_url = db_url.split("@")[-1] if "@" in db_url else "<Masked_URL>"
print(f"嘗試連線至資料庫主機: {masked_url} ...")

try:
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    record = cursor.fetchone()
    print("✅ 連線成功！")
    print(f"PostgreSQL 版本: {record[0]}")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"❌ 連線失敗: {e}")
