"""Fast historical backfill from the official Caixa Mega-Sena API."""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.caixa import fetch_contest, parse_result
from app.db import get_conn, init_db


def fetch_one(contest):
    for attempt in range(3):
        try:
            result = parse_result(fetch_contest(contest))
            n = result["numbers"]
            if len(n) != 6 or len(set(n)) != 6:
                return None
            return result
        except Exception as exc:
            if attempt == 2:
                print(f"Falha no concurso {contest}: {exc}", flush=True)
            else:
                time.sleep(0.5 * (attempt + 1))
    return None


def main():
    init_db()
    latest = parse_result(fetch_contest())["contest"]
    print(f"Último concurso informado pela CAIXA: {latest}", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(fetch_one, contest) for contest in range(1, latest + 1)]
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result:
                results.append(result)
            if i % 200 == 0:
                print(f"Consultados: {i}/{latest}", flush=True)

    results.sort(key=lambda x: x["contest"])
    inserted = 0
    with get_conn() as conn:
        for result in results:
            n = result["numbers"]
            cur = conn.execute(
                "INSERT INTO draws (contest, draw_date, n1,n2,n3,n4,n5,n6) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (contest) DO NOTHING",
                (result["contest"], result["draw_date"], *n),
            )
            inserted += cur.rowcount
        conn.commit()

        row = conn.execute(
            "SELECT COUNT(*) AS total, MIN(contest) AS first_contest, "
            "MAX(contest) AS last_contest, MIN(draw_date) AS first_date, "
            "MAX(draw_date) AS last_date FROM draws"
        ).fetchone()

    print(
        f"Concluído. Concursos processados: {len(results)}; novos inseridos: {inserted}; "
        f"banco: total={row[0]}, primeiro={row[1]} ({row[3]}), "
        f"último={row[2]} ({row[4]})",
        flush=True,
    )


if __name__ == "__main__":
    main()
