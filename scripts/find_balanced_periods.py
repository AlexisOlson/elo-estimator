#!/usr/bin/env python3
"""
Find balanced period split by testing different year boundaries.
Goal: Two periods with similar total game counts.
"""

import requests
import time

MASTERS_URL = "https://explorer.lichess.ovh/masters"
HEADERS = {"User-Agent": "opening-sampler/1.0 (research)"}
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def get_game_count(since, until):
    """Get total game count for a period."""
    params = {"fen": START_FEN, "since": since, "until": until, "moves": 1}
    r = requests.get(MASTERS_URL, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    time.sleep(0.2)

    data = r.json()
    total = data["white"] + data["draws"] + data["black"]
    return total


def find_balanced_split(start_year=1952, end_year=2024):
    """Find the split point that balances game counts."""
    print(f"Testing period splits from {start_year} to {end_year}...")
    print(f"{'Split Year':<12} {'Period A Games':<18} {'Period B Games':<18} {'Ratio':<10} {'Balance'}")
    print("=" * 80)

    best_split = None
    best_ratio = float('inf')

    # Test splits every 2 years
    for split_year in range(start_year + 10, end_year - 10, 2):
        try:
            count_a = get_game_count(start_year, split_year)
            count_b = get_game_count(split_year + 1, end_year)

            ratio = max(count_a, count_b) / min(count_a, count_b) if min(count_a, count_b) > 0 else float('inf')
            balance = abs(count_a - count_b)

            marker = " <-- Best so far" if ratio < best_ratio else ""
            print(f"{split_year:<12} {count_a:>15,}   {count_b:>15,}   {ratio:>8.2f}   {balance:>12,}{marker}")

            if ratio < best_ratio:
                best_ratio = ratio
                best_split = (start_year, split_year, split_year + 1, end_year, count_a, count_b)

        except Exception as e:
            print(f"{split_year:<12} Error: {e}")
            continue

    print("\n" + "=" * 80)
    if best_split:
        a_start, a_end, b_start, b_end, count_a, count_b = best_split
        print(f"\nBest balanced split:")
        print(f"  Period A: {a_start}-{a_end} ({count_a:,} games)")
        print(f"  Period B: {b_start}-{b_end} ({count_b:,} games)")
        print(f"  Ratio: {best_ratio:.2f}:1")
        print(f"  Difference: {abs(count_a - count_b):,} games")

    return best_split


def test_specific_periods():
    """Test some specific period combinations."""
    print("\n" + "=" * 80)
    print("TESTING SPECIFIC PERIOD COMBINATIONS")
    print("=" * 80)

    test_cases = [
        (1952, 1999, 2000, 2024, "Original 1000games split"),
        (1952, 2005, 2006, 2024, "~Midpoint"),
        (1952, 2010, 2011, 2024, "2010 split"),
        (1980, 2005, 2006, 2024, "Modern era only"),
        (2000, 2011, 2012, 2023, "Recent 24 years"),
    ]

    for a_start, a_end, b_start, b_end, desc in test_cases:
        try:
            count_a = get_game_count(a_start, a_end)
            count_b = get_game_count(b_start, b_end)
            ratio = max(count_a, count_b) / min(count_a, count_b) if min(count_a, count_b) > 0 else float('inf')

            print(f"\n{desc}")
            print(f"  Period A: {a_start}-{a_end}: {count_a:>10,} games")
            print(f"  Period B: {b_start}-{b_end}: {count_b:>10,} games")
            print(f"  Ratio: {ratio:.2f}:1")
        except Exception as e:
            print(f"\n{desc}: Error - {e}")


def main():
    print("Finding balanced period split for Masters database...\n")

    # Find best split
    best_split = find_balanced_split(1952, 2024)

    # Also test some specific periods of interest
    test_specific_periods()

    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if best_split:
        a_start, a_end, b_start, b_end, count_a, count_b = best_split
        print(f"\nUse these periods for balanced comparison:")
        print(f"  python scripts/fetch_split_period.py --period-a {a_start} {a_end} --period-b {b_start} {b_end}")


if __name__ == "__main__":
    main()
