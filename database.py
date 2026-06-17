import os
import psycopg2
from psycopg2 import pool
from config import Config

# Failure injection control
_db_outage_simulated = False
_connection_pool = None

def set_db_outage(status: bool):
    """Toggles database outage simulation for testing Ghost Mode and Health Monitors."""
    global _db_outage_simulated
    _db_outage_simulated = status

def init_pool():
    """Initializes the database connection pool."""
    global _connection_pool
    if _db_outage_simulated:
        raise psycopg2.OperationalError("Simulated database outage (pre-initialization check)")
    
    if _connection_pool is None:
        try:
            _connection_pool = pool.SimpleConnectionPool(
                1, 20,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                options=f"-c timezone={Config.TIMEZONE}"
            )
        except Exception as e:
            print(f"Error initializing database pool: {e}")
            raise

def get_connection():
    """Gets a connection from the pool, honoring simulated outage flags."""
    global _db_outage_simulated
    if _db_outage_simulated:
        raise psycopg2.OperationalError("Simulated database outage")
    
    if _connection_pool is None:
        init_pool()
        
    try:
        return _connection_pool.getconn()
    except Exception as e:
        if _db_outage_simulated:
            raise psycopg2.OperationalError("Simulated database outage")
        raise e

def release_connection(conn):
    """Releases a connection back to the pool."""
    if _connection_pool and conn:
        _connection_pool.putconn(conn)

def init_db(schema_path="schema.sql"):
    """Reads and executes schema.sql to initialize all 16 tables."""
    if _db_outage_simulated:
        raise psycopg2.OperationalError("Simulated database outage during init_db")
        
    conn = get_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cursor:
            # Read schema file
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            # Execute SQL script
            cursor.execute(schema_sql)
            print("Database initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        raise
    finally:
        release_connection(conn)

def execute_query(query, params=None, fetch=False):
    """Helper method to run a database query with standard pool management."""
    if _db_outage_simulated:
        raise psycopg2.OperationalError("Simulated database outage")
        
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch:
            result = cursor.fetchall()
        else:
            result = None
        conn.commit()
        return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        if cursor:
            cursor.close()
        release_connection(conn)
