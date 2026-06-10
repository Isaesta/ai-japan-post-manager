import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

with psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
) as conn:

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                id,
                title,
                category,
                post_count
            FROM posts
            ORDER BY id
        """)

        rows = cur.fetchall()

        for row in rows:
            print(row)
