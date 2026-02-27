import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("❌ ERROR: DATABASE_URL is not set.")
    exit(1)

alter_sql = """
ALTER TABLE trade_history 
ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(100);
"""

try:
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    print("Applying ALTER TABLE statement to add 'exit_reason' column...")
    cursor.execute(alter_sql)
    conn.commit()
    print("✅ Successfully added 'exit_reason' column to trade_history table.")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"❌ Failed to run migration: {e}")
