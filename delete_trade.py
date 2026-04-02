import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL")
print(f"Connecting to: {db_url}")
conn = psycopg2.connect(db_url)
print("Connected.")
cursor = conn.cursor()
cursor.execute("SET statement_timeout = 3000;")
try:
    cursor.execute("DELETE FROM trade_history WHERE strategy_name LIKE '%Opt%';")
    conn.commit()
    print("Optimization records deleted successfully!")
except Exception as e:
    print(f"Error: {e}")
finally:
    cursor.close()
    conn.close()
