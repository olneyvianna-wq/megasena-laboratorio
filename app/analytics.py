from collections import Counter
from itertools import combinations
import math
import numpy as np

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
