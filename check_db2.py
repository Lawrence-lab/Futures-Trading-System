import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("DATABASE_URL")
print("Connecting to DB...")
try:
    conn = psycopg2.connect(db_url, connect_timeout=10)
    print("Connected!")
    c = conn.cursor()
    c.execute("SET statement_timeout = 5000;")
    c.execute("SELECT id, strategy_name, to_char(entry_time, 'YYYY-MM-DD HH24:MI') FROM trade_history ORDER BY id DESC LIMIT 50;")
    rows = c.fetchall()
    print("Recent trades:")
    for row in rows:
        print(row)
    c.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
