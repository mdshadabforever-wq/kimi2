import psycopg2

passwords = [
    "postgres", "admin", "root", "password", "123456", "1234", "postgres123", "manager",
    "admin123", "root123", "12345678", "123456789", "123", "qwerty", "postgres1234",
    "iiis", "iiis_user", "iiis_password", "strong_password_here", "strong_password",
    "password123", "pass", "secret", "master", "database", "db", "postgre", "pg",
    "pgadmin", "pgadmin4", "system", "oracle", "sa", "sql", "12345", "1111", "0000"
]

success = False
for pwd in passwords:
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="postgres",
            user="postgres",
            password=pwd,
            connect_timeout=2
        )
        print(f"SUCCESS! Connected using password: '{pwd}'")
        success = True
        conn.close()
        break
    except Exception as e:
        pass

if not success:
    print("Could not connect with common passwords list.")
