import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL found.")
    exit(1)

print(f"Connecting to: {db_url}")
conn = psycopg2.connect(db_url)
print("Connected.")
cursor = conn.cursor()
cursor.execute("SET statement_timeout = 5000;")
try:
    cursor.execute("DELETE FROM trade_history WHERE strategy_name LIKE '%_Backtest%' OR strategy_name LIKE '%_60m' OR strategy_name LIKE '%_5m';")
    deleted_rows = cursor.rowcount
    
    conn.commit()
    print(f"Records deleted successfully! Rows affected: {deleted_rows}")
except Exception as e:
    print(f"Error: {e}")
finally:
    cursor.close()
    conn.close()
