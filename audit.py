import json
import psycopg2
from database import get_connection, release_connection

def log_audit(component: str, action: str, result: str, reason: str = None, metadata: dict = None):
    """Appends a log entry to the audit_log table.
    Enforces append-only logic both in code (no update/delete methods)
    and relies on the database trigger to reject modifications.
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        metadata_json = json.dumps(metadata) if metadata else None
        
        query = """
            INSERT INTO audit_log (component, action, result, reason, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, timestamp;
        """
        cursor.execute(query, (component, action, result, reason, metadata_json))
        inserted = cursor.fetchone()
        conn.commit()
        return inserted
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Failed to log audit event: {e}")
        # Re-raise so calling components know log integrity is compromised
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn:
            release_connection(conn)
