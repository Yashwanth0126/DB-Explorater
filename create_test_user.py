import psycopg2

conn = psycopg2.connect(
    host="dpg-da10dke417fc73fgeqcg-a.oregon-postgres.render.com",
    port=5432,
    dbname="credential_rotation",
    user="credential_rotation_user",
    password="9uiLooEZl8tGNdEC2e6BetCD9ViMEOoK",
)
conn.autocommit = True

with conn.cursor() as cur:
    cur.execute("CREATE USER rotation_test_user WITH PASSWORD 'initial_test_pw_123' LOGIN;")
    cur.execute("GRANT CONNECT ON DATABASE credential_rotation TO rotation_test_user;")

print("Done: rotation_test_user created.")
conn.close()