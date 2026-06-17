import psycopg2

passwords = ["", "postgres", "admin", "root", "password", "123456", "1234", "postgres123", "manager"]
success = False

for pwd in passwords:
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
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
