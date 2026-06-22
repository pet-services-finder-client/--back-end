import asyncio
import os

import asyncpg
import pandas as pd
from google.cloud import bigquery

PROJECT_ID = "analytics-prod-499915"
DATASET = "analytics"

TABLES = [
    "businesses",
    "business_categories",
    "services",
    "animal_types",
    "reviews",
    "pets",
]


def get_sync_database_url() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def fetch_table(conn: asyncpg.Connection, table_name: str) -> pd.DataFrame:
    rows = await conn.fetch(f"SELECT * FROM {table_name}")
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(row) for row in rows])


def upload_to_bigquery(df: pd.DataFrame, table_name: str) -> None:
    if df.empty:
        print(f"Skipping {table_name}: no rows")
        return

    client = bigquery.Client(project=PROJECT_ID)
    table_id = f"{PROJECT_ID}.{DATASET}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    print(f"Uploaded {len(df)} rows to {table_id}")


async def main() -> None:
    db_url = get_sync_database_url()

    conn = None
    last_error = None

    for attempt in range(5):
        try:
            conn = await asyncpg.connect(db_url, ssl="require", timeout=20)
            print(f"Connected on attempt {attempt + 1}")
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            last_error = e

    if conn is None:
        raise last_error

    try:
        for table_name in TABLES:
            df = await fetch_table(conn, table_name)
            upload_to_bigquery(df, table_name)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
