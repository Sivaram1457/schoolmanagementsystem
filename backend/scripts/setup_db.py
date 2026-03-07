"""Check PostgreSQL connectivity and create school_db if needed."""
import psycopg2
import sys

# Try common default passwords for winget-installed PostgreSQL
passwords = ["postgres", "root", "password", ""]

for pwd in passwords:
    try:
        conn = psycopg2.connect(dbname="postgres", user="postgres", password=pwd, host="localhost", port=5432)
        conn.autocommit = True
        print(f"CONNECTED (password='{pwd}')")
        cur = conn.cursor()
        cur.execute("SELECT datname FROM pg_database WHERE datname='school_db'")
        exists = cur.fetchone()
        if exists:
            print("school_db already exists")
        else:
            cur.execute("CREATE DATABASE school_db")
            print("school_db CREATED")
        cur.close()
        conn.close()
        sys.exit(0)
    except psycopg2.OperationalError as e:
        err = str(e)
        if "password authentication failed" in err:
            print(f"  password '{pwd}' failed, trying next...")
            continue
        elif "connection refused" in err or "could not connect" in err:
            print(f"ERROR: PostgreSQL not accepting connections: {e}")
            sys.exit(1)
        else:
            print(f"ERROR: {e}")
            sys.exit(1)

print("ERROR: None of the default passwords worked.")
print("Please set the postgres password and update .env accordingly.")
sys.exit(1)
