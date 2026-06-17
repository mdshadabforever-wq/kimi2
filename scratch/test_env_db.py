import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import psycopg2
from config import Config

try:
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    print("SUCCESS! Connected using .env credentials!")
    conn.close()
except Exception as e:
    print(f"FAILED to connect using .env credentials: {e}")
