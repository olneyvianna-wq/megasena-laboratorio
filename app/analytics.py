from collections import Counter
from itertools import combinations
import math
from datetime import date, timedelta
import numpy as np
from scipy.stats import chisquare, kruskal

TOTAL_COMBINATIONS = math.comb(60, 6)


def combination_probability():
    return {"total_combinations": TOTAL_COMBINATIONS, "probability": f"1/{TOTAL_COMBINATIONS}"}


def normalize_numbers(numbers):
    nums = sorted(int(x) for x in numbers)
    if len(nums) != 6 or len(set(nums)) != 6 or any(x < 1 or x > 60 for x in nums):
        raise ValueError("Um concurso deve conter 6 dezenas distintas entre 1 e 60.")
    return nums


def draw_features(numbers):
    nums = normalize_numbers(numbers)
    return {
        "numbers": nums,
        "sum": int(sum(nums)),
        "odd": sum(n % 2 for n in nums),
        "even": sum(n % 2 == 0 for n in nums),
        "low_1_30": sum(n <= 30 for n in nums),
        "high_31_60": sum(n >= 31 for n in nums),
        "consecutive_pairs": sum(b == a + 1 for a, b in zip(nums, nums[1:])),
        "decades": [sum((n - 1) // 10 == d for n in nums) for d in range(6)],
    }


def frequencies(draws):
    counter = Counter()
    for draw in draws:
        counter.update(normalize_numbers(draw))
    return [{"number": n, "count": counter[n]} for n in range(1, 61)]


def pair_frequencies(draws, top_n=30):
    counter = Counter()
    for draw in draws:
        counter.update(combinations(normalize_numbers(draw), 2))
    return [{"pair": list(pair), "count": count} for pair, count in counter.most_common(top_n)]


def summary(draws):
    if not draws:
        return {"draws": 0}
    features = [draw_features(d) for d in draws]
    sums = np.array([x["sum"] for x in features])
    odds = Counter(x["odd"] for x in features)
    low_high = Counter((x["low_1_30"], x["high_31_60"]) for x in features)
    consecutive = Counter(x["consecutive_pairs"] for x in features)
    decade_totals = [sum(x["decades"][i] for x in features) for i in range(6)]
    return {
        "draws": len(draws),
        "sum": {"mean": float(sums.mean()), "std": float(sums.std(ddof=1)), "min": int(sums.min()), "max": int(sums.max()), "median": float(np.median(sums))},
        "odd_even": {str(k): v for k, v in sorted(odds.items())},
        "low_high": {f"{k[0]}x{k[1]}": v for k, v in sorted(low_high.items())},
        "consecutive_pairs": {str(k): v for k, v in sorted(consecutive.items())},
        "decade_occurrences": {str((i + 1) * 10): decade_totals[i] for i in range(6)},
        "expected_frequency_per_number": len(draws) * 6 / 60,
    }


def statistical_report(draws):
    freq = frequencies(draws)
    ranked = sorted(freq, key=lambda x: (-x["count"], x["number"]))
    least = sorted(freq, key=lambda x: (x["count"], x["number"]))
    return {
        "probability": combination_probability(),
        "summary": summary(draws),
        "frequencies": freq,
        "most_frequent": ranked[:10],
        "least_frequent": least[:10],
        "pairs_top_30": pair_frequencies(draws, 30),
    }


def _zodiac(month, day):
    # Tropical zodiac with conventional boundaries.
    md = (month, day)
    boundaries = [
        ((1, 20), "Aquario"),
        ((2, 19), "Peixes"),
        ((3, 21), "Aries"),
        ((4, 20), "Touro"),
        ((5, 21), "Gemeos"),
        ((6, 21), "Cancer"),
        ((7, 23), "Leao"),
        ((8, 23), "Virgem"),
        ((9, 23), "Libra"),
        ((10, 23), "Escorpiao"),
        ((11, 22), "Sagitario"),
        ((12, 22), "Capricornio"),
    ]
    for i in range(len(boundaries) - 1, -1, -1):
        if md >= boundaries[i][0]:
            return boundaries[i][1]
    return "Capricornio"


def _easter_sunday(year):
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _holiday_name(d):
    fixed = {
        (1, 1): "Confraternizacao Universal",
        (4, 21): "Tiradentes",
        (5, 1): "Dia do Trabalho",
        (9, 7): "Independencia",
        (10, 12): "Nossa Senhora Aparecida",
        (11, 2): "Finados",
        (11, 15): "Proclamacao da Republica",
        (11, 20): "Consciencia Negra",
        (12, 25): "Natal",
    }
    if (d.month, d.day) in fixed:
        return fixed[(d.month, d.day)]
    easter = _easter_sunday(d.year)
    movable = {
        easter - timedelta(days=47): "Carnaval",
        easter - timedelta(days=2): "Sexta-feira Santa",
        easter - timedelta(days=60): "Corpus Christi",
    }
    return movable.get(d)


def _group_report(draws, dates, key_fn):
    groups = {}
    for draw, d in zip(draws, dates):
        key = key_fn(d)
        groups.setdefault(key, []).append(draw)

    out = {}
    for key, subset in sorted(groups.items(), key=lambda kv: str(kv[0])):
        feats = [draw_features(x) for x in subset]
        sums = np.array([f["sum"] for f in feats], dtype=float)
        out[str(key)] = {
            "draws": len(subset),
            "sum_mean": float(sums.mean()),
            "odd_mean": float(np.mean([f["odd"] for f in feats])),
            "number_frequency": frequencies(subset),
        }
    return out


def calendar_report(records):
    if not records:
        return {"draws": 0}

    records = sorted(records, key=lambda r: r[0])
    dates = [r[1] for r in records]
    draws = [r[2] for r in records]

    weekday = _group_report(draws, dates, lambda d: d.strftime("%A"))
    day_parity = _group_report(draws, dates, lambda d: "par" if d.day % 2 == 0 else "impar")
    month = _group_report(draws, dates, lambda d: d.month)
    day_of_month = _group_report(draws, dates, lambda d: d.day)
    zodiac = _group_report(draws, dates, lambda d: _zodiac(d.month, d.day))

    holiday_groups = {}
    for draw, d in zip(draws, dates):
        name = _holiday_name(d) or "dia_comum"
        holiday_groups.setdefault(name, []).append(draw)
    holiday = {
        name: {
            "draws": len(subset),
            "sum_mean": float(np.mean([sum(normalize_numbers(x)) for x in subset])),
            "number_frequency": frequencies(subset),
        }
        for name, subset in sorted(holiday_groups.items())
    }

    association_tests = {}
    for label, groups in {
        "weekday": weekday, "day_parity": day_parity, "month": month,
        "day_of_month": day_of_month, "zodiac": zodiac, "holiday": holiday,
    }.items():
        tests = []
        for group, info in groups.items():
            counts = np.array([x["count"] for x in info["number_frequency"]], dtype=float)
            expected = np.full(60, counts.sum() / 60.0)
            chi = chisquare(counts, expected)
            tests.append({
                "group": group,
                "chi2": float(chi.statistic),
                "p_value": float(chi.pvalue),
                "n_draws": info["draws"],
            })
        m = max(1, len(tests))
        for t in tests:
            t["p_value_bonferroni"] = min(1.0, t["p_value"] * m)
        association_tests[label] = tests

    weekday_counts = Counter(d.strftime("%A") for d in dates)
    parity_counts = Counter("par" if d.day % 2 == 0 else "impar" for d in dates)
    month_counts = Counter(d.month for d in dates)
    zodiac_counts = Counter(_zodiac(d.month, d.day) for d in dates)
    holiday_counts = Counter(_holiday_name(d) or "dia_comum" for d in dates)

    def kw(groups):
        vals = [np.array([sum(normalize_numbers(x)) for x in subset], dtype=float) for subset in groups if len(subset) >= 2]
        if len(vals) < 2:
            return {"statistic": None, "p_value": None}
        r = kruskal(*vals)
        return {"statistic": float(r.statistic), "p_value": float(r.pvalue)}

    return {
        "draws": len(draws),
        "calendar_counts": {
            "weekday": dict(weekday_counts),
            "day_parity": dict(parity_counts),
            "month": dict(month_counts),
            "zodiac": dict(zodiac_counts),
            "holiday": dict(holiday_counts),
        },
        "groups": {
            "weekday": weekday,
            "day_parity": day_parity,
            "month": month,
            "day_of_month": day_of_month,
            "zodiac": zodiac,
            "holiday": holiday,
        },
        "association_tests": association_tests,
        "sum_effect_tests": {
            "weekday_kruskal": kw([x for x in _group_report(draws, dates, lambda d: d.strftime("%A")).values()]),
            "month_kruskal": kw([x for x in _group_report(draws, dates, lambda d: d.month).values()]),
            "zodiac_kruskal": kw([x for x in _group_report(draws, dates, lambda d: _zodiac(d.month, d.day)).values()]),
        },
        "method_note": "p-values are screening evidence, not proof of predictability; calendar variables can be confounded by the official draw schedule and multiple testing.",
    }
