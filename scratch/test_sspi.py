import psycopg2

try:
    # Connect without specifying user/password to use active OS user (SSPI)
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="postgres"
    )
    print("SUCCESS! Connected via SSPI/Peer authentication!")
    conn.close()
except Exception as e:
    print(f"FAILED to connect via SSPI: {e}")
