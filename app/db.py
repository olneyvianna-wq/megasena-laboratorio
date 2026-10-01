import os
from contextlib import contextmanager
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")

@contextmanager
def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada")
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn

def init_db():
    from pathlib import Path
    sql = Path(__file__).resolve().parent.parent / "sql" / "001_schema.sql"
    with get_conn() as conn:
        conn.execute(sql.read_text(encoding="utf-8"))
        conn.commit()
