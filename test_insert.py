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
        cur.execute(
            """
            INSERT INTO posts (title, category, content, image_path)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (
                "テスト投稿",
                "日常観察",
                "これはPythonから登録したテスト投稿です。",
                None,
            ),
        )

        new_id = cur.fetchone()[0]
        print(f"登録成功: id={new_id}")
