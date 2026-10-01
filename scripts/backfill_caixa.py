"""Fast historical backfill from the official Caixa Mega-Sena API."""
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.caixa import fetch_contest, parse_result
from app.db import get_conn, init_db

def fetch_one(contest):
    try:
        result = parse_result(fetch_contest(contest))
        n = result["numbers"]
        if len(n) != 6 or len(set(n)) != 6:
            return None
        return result
    except Exception as exc:
        print(f"Falha no concurso {contest}: {exc}", flush=True)
        return None

def main():
    init_db()
    latest = parse_result(fetch_contest())["contest"]
    print(f"Último concurso informado pela CAIXA: {latest}", flush=True)

    inserted = 0
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
    with get_conn() as conn:
        for result in results:
            n = result["numbers"]
            cur = conn.execute(
                "INSERT INTO draws (contest, draw_date, n1,n2,n3,n4,n5,n6) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (contest) DO NOTHING",
                (result["contest"], result["draw_date"], *n),
            )
            inserted += cur.rowcount
        conn.commit()

    print(f"Concluído. Concursos processados: {len(results)}; novos inseridos: {inserted}", flush=True)

if __name__ == "__main__":
    main()
