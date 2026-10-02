"""Fast historical backfill from the official Caixa Mega-Sena API."""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.caixa import fetch_contest, parse_result
from app.db import get_conn, init_db


def fetch_with_retry(contest=None, attempts=5):
    for attempt in range(1, attempts + 1):
        try:
            return parse_result(fetch_contest(contest))
        except Exception as exc:
            if attempt == attempts:
                raise
            wait = min(8.0, 0.75 * (2 ** (attempt - 1)))
            print(f"Tentativa {attempt}/{attempts} falhou para {contest or 'ultimo'}: {exc}; aguardando {wait:.1f}s", flush=True)
            time.sleep(wait)


def fetch_one(contest):
    try:
        result = fetch_with_retry(contest)
        n = result["numbers"]
        if len(n) != 6 or len(set(n)) != 6:
            raise ValueError("resultado invalido")
        return result
    except Exception as exc:
        print(f"Falha no concurso {contest}: {exc}", flush=True)
        return None


def main():
    init_db()
    try:
        latest = fetch_with_retry()["contest"]
    except Exception as exc:
        # A ingestao nao deve impedir o servico de subir quando a API externa estiver fora.
        print(f"AVISO: CAIXA indisponivel no momento ({exc}). Backfill adiado.", flush=True)
        return

    print(f"Ultimo concurso informado pela CAIXA: {latest}", flush=True)

    with get_conn() as conn:
        existing = {r[0] for r in conn.execute("SELECT contest FROM draws").fetchall()}
    missing = [c for c in range(1, latest + 1) if c not in existing]
    print(f"Concursos existentes no banco: {len(existing)}; faltantes: {len(missing)}", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch_one, contest) for contest in missing]
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result:
                results.append(result)
            if i % 100 == 0:
                print(f"Consultados: {i}/{len(missing)}", flush=True)

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
        f"Concluido. Processados: {len(results)}; novos inseridos: {inserted}; "
        f"banco: total={row[0]}, primeiro={row[1]} ({row[3]}), "
        f"ultimo={row[2]} ({row[4]})",
        flush=True,
    )


if __name__ == "__main__":
    main()
