"""Backfill the historical Mega-Sena draws from the Caixa API.

Usage:
    DATABASE_URL='...' python scripts/backfill_caixa.py

The script first reads the current contest from Caixa, then requests
contests 1..latest and inserts them idempotently.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.caixa import fetch_contest, parse_result
from app.db import get_conn, init_db

def main():
    init_db()
    latest = parse_result(fetch_contest())["contest"]
    print(f"Último concurso informado pela CAIXA: {latest}")

    inserted = 0
    errors = 0

    with get_conn() as conn:
        for contest in range(1, latest + 1):
            try:
                result = parse_result(fetch_contest(contest))
                n = result["numbers"]
                if len(n) != 6 or len(set(n)) != 6:
                    raise ValueError("resultado inválido")

                cur = conn.execute(
                    """INSERT INTO draws
                       (contest, draw_date, n1,n2,n3,n4,n5,n6)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (contest) DO NOTHING""",
                    (result["contest"], result["draw_date"], *n),
                )
                inserted += cur.rowcount
                if contest % 100 == 0:
                    conn.commit()
                    print(f"{contest}/{latest} — novos: {inserted}")
                time.sleep(0.05)
            except Exception as exc:
                errors += 1
                print(f"Falha no concurso {contest}: {exc}")

        conn.commit()

    print(f"Concluído. Inseridos: {inserted}; erros: {errors}")

if __name__ == "__main__":
    main()
