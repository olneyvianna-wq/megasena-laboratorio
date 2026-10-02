import io
import os
import threading
from fastapi import FastAPI, HTTPException, UploadFile, File
import pandas as pd

from .db import get_conn, init_db
from .analytics import combination_probability, frequencies, pair_frequencies, summary, statistical_report, calendar_report
from .caixa import fetch_contest, parse_result

app = FastAPI(title="Mega-Sena Laboratório", version="0.3.0", description="API para análise estatística dos concursos da Mega-Sena.")

@app.on_event("startup")
def startup():
    init_db()
    if os.getenv("BACKFILL_ON_STARTUP", "false").lower() == "true":
        threading.Thread(target=_background_backfill, daemon=True).start()

def _background_backfill():
    try:
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
