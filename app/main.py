import io
import os
import threading
import json
from collections import Counter
from statistics import mean, median, multimode, pstdev
from fastapi import FastAPI, HTTPException, UploadFile, File
import pandas as pd

from .db import get_conn, init_db
from .analytics import combination_probability, frequencies, pair_frequencies, summary, statistical_report, calendar_report, independence_report, monte_carlo_report, ordered_universes_report, realizables_report

app = FastAPI(title="Mega-Sena Laboratório", version="0.4.0", description="API para análise estatística dos concursos da Mega-Sena.")

@app.on_event("startup")
def startup():
    init_db()
    _startup_report()
    if os.getenv("BACKFILL_ON_STARTUP", "false").lower() == "true":
        threading.Thread(target=_background_backfill, daemon=True).start()

def _startup_report():
    try:
        with get_conn() as conn:
            rows = conn.execute("SELECT contest, draw_date, n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest").fetchall()
        draws = [list(r[2:]) for r in rows]
        records = [(r[0], r[1], list(r[2:])) for r in rows if r[1] is not None]
        report = statistical_report(draws)
        cal = calendar_report(records)
        meta = {
            "draws": len(draws),
            "first_contest": rows[0][0] if rows else None,
            "last_contest": rows[-1][0] if rows else None,
            "first_date": rows[0][1].isoformat() if rows and rows[0][1] else None,
            "last_date": rows[-1][1].isoformat() if rows and rows[-1][1] else None,
        }
        top = report["most_frequent"]
        print("MEGASENA_REPORT_001=" + json.dumps({
            "database": meta,
            "probability": report["probability"],
            "summary": report["summary"],
            "most_frequent": top,
            "least_frequent": report["least_frequent"],
            "pairs_top_30": report["pairs_top_30"],
            "calendar_counts": cal.get("calendar_counts", {}),
            "sum_effect_tests": cal.get("sum_effect_tests", {}),
            "association_tests": cal.get("association_tests", {}),
            "independence": independence_report(draws),
        }, ensure_ascii=False, separators=(",", ":")), flush=True)
    except Exception as exc:
        print(f"MEGASENA_REPORT_001_ERROR={exc}", flush=True)

def _background_backfill():
    try:
        from .caixa import fetch_contest, parse_result
        latest = parse_result(fetch_contest())["contest"]
        with get_conn() as conn:
            for contest in range(1, latest + 1):
                try:
                    result = parse_result(fetch_contest(contest))
                    n = result["numbers"]
                    if len(n) != 6 or len(set(n)) != 6:
                        continue
                    conn.execute("INSERT INTO draws (contest, draw_date, n1,n2,n3,n4,n5,n6) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (contest) DO NOTHING", (result["contest"], result["draw_date"], *n))
                    if contest % 50 == 0:
                        conn.commit()
                except Exception:
                    continue
            conn.commit()
    except Exception:
        pass

@app.get("/")
def root():
    return {"name": "Mega-Sena Laboratório", "status": "online", "message": "Laboratório estatístico — análise não é previsão."}

@app.get("/health")
def health():
    with get_conn() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}

@app.get("/stats/probability")
def probability():
    return combination_probability()

@app.get("/draws/count")
def draws_count():
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM draws").fetchone()
    return {"draws": row[0]}

@app.get("/stats/summary")
def stats_summary():
    with get_conn() as conn:
        rows = conn.execute("SELECT n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest").fetchall()
    return summary([list(r) for r in rows])

@app.get("/stats/frequencies")
def stats_frequencies():
    with get_conn() as conn:
        rows = conn.execute("SELECT n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest").fetchall()
    return {"frequencies": frequencies([list(r) for r in rows])}

@app.get("/stats/pairs")
def stats_pairs(top_n: int = 30):
    if top_n < 1 or top_n > 500:
        raise HTTPException(400, "top_n deve estar entre 1 e 500.")
    with get_conn() as conn:
        rows = conn.execute("SELECT n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest").fetchall()
    return {"pairs": pair_frequencies([list(r) for r in rows], top_n)}

@app.get("/stats/report")
def stats_report():
    with get_conn() as conn:
        rows = conn.execute("SELECT n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest").fetchall()
        meta = conn.execute("SELECT COUNT(*), MIN(contest), MAX(contest), MIN(draw_date), MAX(draw_date) FROM draws").fetchone()
    draws = [list(r) for r in rows]
    report = statistical_report(draws)
    report["database"] = {"draws": meta[0], "first_contest": meta[1], "last_contest": meta[2], "first_date": meta[3].isoformat() if meta[3] else None, "last_date": meta[4].isoformat() if meta[4] else None}
    return report

@app.get("/stats/independence")
def stats_independence():
    with get_conn() as conn:
        rows = conn.execute("SELECT n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest").fetchall()
    return independence_report([list(r) for r in rows])

@app.get("/stats/realizables")
def stats_realizables():
    with get_conn() as conn:
        rows = conn.execute("SELECT n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest").fetchall()
    return realizables_report([list(r) for r in rows])

@app.get("/stats/ordered-universes")
def stats_ordered_universes():
    with get_conn() as conn:
        rows = conn.execute("SELECT n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest").fetchall()
    return ordered_universes_report([list(r) for r in rows])

@app.get("/stats/monte-carlo")
def stats_monte_carlo(simulations: int = 200, seed: int = 20261002):
    if simulations < 10 or simulations > 1000:
        raise HTTPException(400, "simulations deve estar entre 10 e 1000.")
    with get_conn() as conn:
        rows = conn.execute("SELECT n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest").fetchall()
    return monte_carlo_report([list(r) for r in rows], simulations=simulations, seed=seed)

@app.get("/stats/calendar")
def stats_calendar():
    with get_conn() as conn:
        rows = conn.execute("SELECT contest, draw_date, n1,n2,n3,n4,n5,n6 FROM draws WHERE draw_date IS NOT NULL ORDER BY contest").fetchall()
    records = [(r[0], r[1], list(r[2:])) for r in rows]
    return calendar_report(records)

@app.get("/draws/latest")
def latest_draws(limit: int = 20):
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit deve estar entre 1 e 500.")
    with get_conn() as conn:
        rows = conn.execute("SELECT contest, draw_date, n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest DESC LIMIT %s", (limit,)).fetchall()
    return {"draws": [{"contest": r[0], "date": r[1].isoformat() if r[1] else None, "numbers": list(r[2:])} for r in rows]}

@app.post("/draws/import-csv")
async def import_csv(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw), sep=None, engine="python")
    except Exception as exc:
        raise HTTPException(400, f"CSV inválido: {exc}")
    normalized = {str(c).strip().lower(): c for c in df.columns}
    required = ["concurso", "data", "bola 1", "bola 2", "bola 3", "bola 4", "bola 5", "bola 6"]
    if not all(c in normalized for c in required):
        raise HTTPException(400, "CSV esperado com colunas: Concurso, Data, Bola 1, Bola 2, Bola 3, Bola 4, Bola 5, Bola 6")
    inserted = 0
    with get_conn() as conn:
        for _, row in df.iterrows():
            values = (int(row[normalized["concurso"]]), pd.to_datetime(row[normalized["data"]], dayfirst=True).date(), *[int(row[normalized[f"bola {i}"]] ) for i in range(1, 7)])
            result = conn.execute("INSERT INTO draws (contest, draw_date, n1,n2,n3,n4,n5,n6) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (contest) DO NOTHING", values)
            inserted += result.rowcount
        conn.commit()
    return {"received": len(df), "inserted": inserted}


@app.get("/admin/verify-position-universes")
def verify_position_universes():
    """Verifica materialização e retorna somente os resultados essenciais das seis casas."""
    tables = [
        "ur_primeira_casa", "ur_segunda_casa", "ur_terceira_casa",
        "ur_quarta_casa", "ur_quinta_casa", "ur_sexta_casa"
    ]
    with get_conn() as conn:
        exists = {}
        for table in tables + ["ur_posicao_resumo", "ur_transicoes_numero", "ur_transicoes_caracteristicas"]:
            row = conn.execute(
                "SELECT to_regclass(%s)", (table,)
            ).fetchone()
            exists[table] = row[0] is not None

        if not all(exists.values()):
            return {"status": "incomplete", "tables": exists}

        summaries = conn.execute("""
            SELECT posicao,nome,total_observacoes,minimo,maximo,valores_distintos,
                   media,mediana,moda,desvio_padrao,q1,q3,iqr
            FROM ur_posicao_resumo ORDER BY posicao
        """).fetchall()

        casas = []
        for pos, table in enumerate(tables, start=1):
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            rows = conn.execute(f"""
                SELECT numero,ocorrencias,percentual,percentual_acumulado
                FROM {table} ORDER BY numero
            """).fetchall()
            casas.append({
                "posicao": pos,
                "tabela": table,
                "linhas": count,
                "dados": [
                    {"numero": r[0], "ocorrencias": r[1],
                     "percentual": float(r[2]), "percentual_acumulado": float(r[3])}
                    for r in rows
                ]
            })

        transitions = {
            "numero_linhas": conn.execute("SELECT COUNT(*) FROM ur_transicoes_numero").fetchone()[0],
            "caracteristicas_linhas": conn.execute("SELECT COUNT(*) FROM ur_transicoes_caracteristicas").fetchone()[0]
        }

    return {
        "status": "ok",
        "resumo": [
            {
                "posicao": r[0], "nome": r[1], "total_observacoes": r[2],
                "minimo": r[3], "maximo": r[4], "valores_distintos": r[5],
                "media": float(r[6]), "mediana": float(r[7]), "moda": r[8],
                "desvio_padrao": float(r[9]), "q1": float(r[10]),
                "q3": float(r[11]), "iqr": float(r[12])
            } for r in summaries
        ],
        "casas": casas,
        "transicoes": transitions
    }

@app.post("/admin/build-position-universes")
def build_position_universes():
    """
    Materializa os seis sub-universos posicionais históricos e seus resumos.
    As casas são definidas pela ordenação crescente das seis dezenas de cada concurso.
    Não há filtro de 5% nesta etapa: primeiro registramos a distribuição completa.
    """
    tables = [
        "ur_primeira_casa", "ur_segunda_casa", "ur_terceira_casa",
        "ur_quarta_casa", "ur_quinta_casa", "ur_sexta_casa"
    ]

    def is_prime(n):
        if n < 2:
            return False
        d = 2
        while d * d <= n:
            if n % d == 0:
                return False
            d += 1
        return True

    fibonacci = {1, 2, 3, 5, 8, 13, 21, 34, 55}
    triangular = {1, 3, 6, 10, 15, 21, 28, 36, 45, 55}
    squares = {1, 4, 9, 16, 25, 36, 49}

    def decade(n):
        lo = ((n - 1) // 10) * 10 + 1
        hi = lo + 9
        return f"{lo:02d}-{hi:02d}"

    def props(n):
        return (
            is_prime(n), n % 2 == 0, n % 3 == 0, n % 5 == 0, n % 7 == 0,
            n in squares, n in fibonacci, n in triangular,
            decade(n), sum(int(x) for x in str(n)), n % 10
        )

    with get_conn() as conn:
        raw = conn.execute(
            "SELECT contest, n1,n2,n3,n4,n5,n6 FROM draws ORDER BY contest"
        ).fetchall()

        if not raw:
            raise HTTPException(409, "A tabela draws está vazia.")

        draws = [(r[0], sorted(map(int, r[1:7]))) for r in raw]
        total = len(draws)

        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS {table}")

        conn.execute("DROP TABLE IF EXISTS ur_posicao_resumo")
        conn.execute("DROP TABLE IF EXISTS ur_transicoes_numero")
        conn.execute("DROP TABLE IF EXISTS ur_transicoes_caracteristicas")

        position_sql = """
            CREATE TABLE {table} (
                numero INTEGER PRIMARY KEY,
                ocorrencias INTEGER NOT NULL,
                percentual NUMERIC(12,6) NOT NULL,
                percentual_acumulado NUMERIC(12,6) NOT NULL,
                primo BOOLEAN NOT NULL,
                par BOOLEAN NOT NULL,
                multiplo_3 BOOLEAN NOT NULL,
                multiplo_5 BOOLEAN NOT NULL,
                multiplo_7 BOOLEAN NOT NULL,
                quadrado_perfeito BOOLEAN NOT NULL,
                fibonacci BOOLEAN NOT NULL,
                triangular BOOLEAN NOT NULL,
                faixa_10 TEXT NOT NULL,
                soma_algarismos INTEGER NOT NULL,
                final INTEGER NOT NULL
            )
        """

        for table in tables:
            conn.execute(position_sql.format(table=table))

        conn.execute("""
            CREATE TABLE ur_posicao_resumo (
                posicao SMALLINT PRIMARY KEY,
                nome TEXT NOT NULL,
                total_observacoes INTEGER NOT NULL,
                minimo INTEGER NOT NULL,
                maximo INTEGER NOT NULL,
                valores_distintos INTEGER NOT NULL,
                media NUMERIC(14,8) NOT NULL,
                mediana NUMERIC(14,8) NOT NULL,
                moda TEXT NOT NULL,
                desvio_padrao NUMERIC(14,8) NOT NULL,
                q1 NUMERIC(14,8) NOT NULL,
                q3 NUMERIC(14,8) NOT NULL,
                iqr NUMERIC(14,8) NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE ur_transicoes_numero (
                posicao SMALLINT NOT NULL,
                numero_origem INTEGER NOT NULL,
                numero_destino INTEGER NOT NULL,
                ocorrencias INTEGER NOT NULL,
                percentual NUMERIC(12,6) NOT NULL,
                PRIMARY KEY (posicao, numero_origem, numero_destino)
            )
        """)

        conn.execute("""
            CREATE TABLE ur_transicoes_caracteristicas (
                posicao SMALLINT NOT NULL,
                caracteristica TEXT NOT NULL,
                estado_origem TEXT NOT NULL,
                estado_destino TEXT NOT NULL,
                ocorrencias INTEGER NOT NULL,
                percentual NUMERIC(12,6) NOT NULL,
                PRIMARY KEY (posicao, caracteristica, estado_origem, estado_destino)
            )
        """)

        result = {"total_concursos": total, "casas": {}, "transicoes": {}}

        for idx, table in enumerate(tables):
            pos = idx + 1
            values = [d[1][idx] for d in draws]
            counter = Counter(values)
            ordered = sorted(counter.items())
            cumulative = 0.0
            rows_out = []

            for numero, ocorrencias in ordered:
                pct = ocorrencias / total * 100.0
                cumulative += pct
                p = props(numero)
                conn.execute(
                    f"""INSERT INTO {table}
                    (numero, ocorrencias, percentual, percentual_acumulado, primo, par,
                     multiplo_3, multiplo_5, multiplo_7, quadrado_perfeito, fibonacci,
                     triangular, faixa_10, soma_algarismos, final)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (numero, ocorrencias, pct, cumulative, *p)
                )
                rows_out.append({
                    "numero": numero, "ocorrencias": ocorrencias,
                    "percentual": round(pct, 8),
                    "percentual_acumulado": round(cumulative, 8)
                })

            modes = multimode(values)
            qs = sorted(values)
            if len(qs) >= 2:
                q1 = float(pd.Series(qs).quantile(0.25))
                q3 = float(pd.Series(qs).quantile(0.75))
            else:
                q1 = q3 = float(qs[0])

            summary_row = {
                "posicao": pos,
                "nome": f"{pos}ª casa",
                "total_observacoes": total,
                "minimo": min(values),
                "maximo": max(values),
                "valores_distintos": len(counter),
                "media": float(mean(values)),
                "mediana": float(median(values)),
                "moda": ",".join(map(str, modes)),
                "desvio_padrao": float(pstdev(values)),
                "q1": q1,
                "q3": q3,
                "iqr": q3 - q1
            }
            conn.execute("""
                INSERT INTO ur_posicao_resumo
                (posicao,nome,total_observacoes,minimo,maximo,valores_distintos,media,
                 mediana,moda,desvio_padrao,q1,q3,iqr)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, tuple(summary_row.values()))

            result["casas"][f"casa_{pos}"] = {
                "tabela": table,
                "resumo": summary_row,
                "dados": rows_out
            }

        # Transições entre concursos consecutivos, preservando a sequência temporal.
        number_transitions = Counter()
        property_transitions = Counter()
        property_names = ["paridade", "primo", "faixa_10", "multiplo_3", "multiplo_5", "multiplo_7"]
        for prev, curr in zip(draws, draws[1:]):
            for idx in range(6):
                a, b = prev[1][idx], curr[1][idx]
                number_transitions[(idx + 1, a, b)] += 1
                pa, pb = props(a), props(b)
                states = {
                    "paridade": ("PAR" if pa[1] else "IMPAR", "PAR" if pb[1] else "IMPAR"),
                    "primo": ("PRIMO" if pa[0] else "NAO_PRIMO", "PRIMO" if pb[0] else "NAO_PRIMO"),
                    "faixa_10": (pa[8], pb[8]),
                    "multiplo_3": ("SIM" if pa[2] else "NAO", "SIM" if pb[2] else "NAO"),
                    "multiplo_5": ("SIM" if pa[3] else "NAO", "SIM" if pb[3] else "NAO"),
                    "multiplo_7": ("SIM" if pa[4] else "NAO", "SIM" if pb[4] else "NAO"),
                }
                for name in property_names:
                    sa, sb = states[name]
                    property_transitions[(idx + 1, name, sa, sb)] += 1

        transition_total = total - 1
        for (pos, a, b), count in number_transitions.items():
            pct = count / transition_total * 100.0
            conn.execute(
                """INSERT INTO ur_transicoes_numero
                (posicao,numero_origem,numero_destino,ocorrencias,percentual)
                VALUES (%s,%s,%s,%s,%s)""",
                (pos, a, b, count, pct)
            )

        for (pos, name, a, b), count in property_transitions.items():
            pct = count / transition_total * 100.0
            conn.execute(
                """INSERT INTO ur_transicoes_caracteristicas
                (posicao,caracteristica,estado_origem,estado_destino,ocorrencias,percentual)
                VALUES (%s,%s,%s,%s,%s,%s)""",
                (pos, name, a, b, count, pct)
            )

        conn.commit()

        result["transicoes"] = {
            "concursos_em_sequencia": transition_total,
            "tabelas": ["ur_transicoes_numero", "ur_transicoes_caracteristicas"],
            "observacao": "As transições usam todos os concursos em ordem temporal; não há deduplicação."
        }

    return result

