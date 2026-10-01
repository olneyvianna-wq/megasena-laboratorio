import json
import urllib.request
from datetime import datetime

CAIXA_API = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena"

def fetch_contest(contest: int | None = None) -> dict:
    url = CAIXA_API if contest is None else f"{CAIXA_API}/{contest}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MegaSena-Laboratorio/0.1",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def parse_result(payload: dict) -> dict:
    numbers = sorted(int(x) for x in payload["listaDezenas"])
    return {
        "contest": int(payload["numero"]),
        "draw_date": datetime.strptime(payload["dataApuracao"], "%d/%m/%Y").date(),
        "numbers": numbers,
    }
