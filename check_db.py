import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL found.")
    exit(1)

conn = psycopg2.connect(db_url)
df = pd.read_sql("SELECT id, strategy_name, side, entry_time, entry_reason, exit_time, exit_reason FROM trade_history ORDER BY id DESC LIMIT 5;", conn)
print(df)
conn.close()
