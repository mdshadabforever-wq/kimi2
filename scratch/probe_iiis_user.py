import psycopg2

passwords = ["iiis_user", "iiis", "password", "admin", "postgres", "123456", "iiis_password", "strong_password"]
success = False

for pwd in passwords:
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="iiis",
            user="iiis_user",
            password=pwd,
            connect_timeout=2
        )
        print(f"SUCCESS! Connected using password: '{pwd}'")
        success = True
        conn.close()
        break
    except Exception as e:
        print(f"Failed with password '{pwd}': {e}")

if not success:
    print("Could not connect with any common password.")
