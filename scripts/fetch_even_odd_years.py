#!/usr/bin/env python3
"""
Fetch masters data split by even/odd years to measure true transposition noise
without temporal drift confounding.
"""

import sys
import csv
from pathlib import Path
from lichess_masters import fetch_counts, children_sorted_by_info
import time
import math
from collections import deque


def aggregate_years(year_list, N=1000, M0=500, decay=0.6, Mmin=40, max_depth=20):
    """
    Aggregate data across multiple years by making multiple API calls.
    For each position, we sum the WDL counts across all years.
    """
    print(f"Aggregating data for years: {year_list[0]}-{year_list[-1]} (even/odd)")

    start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    # Get root position aggregated across all years
    root = {"white": 0, "draws": 0, "black": 0, "moves": {}}

    print("Fetching root position...")
    for year in year_list:
        try:
            data = fetch_counts(start_fen, year, year, moves=40)
            root["white"] += data["white"]
            root["draws"] += data["draws"]
            root["black"] += data["black"]

            # Aggregate moves
            for mv in data.get("moves", []):
                key = mv["san"]
                if key not in root["moves"]:
                    root["moves"][key] = {"san": mv["san"], "uci": mv.get("uci", ""),
                                          "white": 0, "draws": 0, "black": 0}
                root["moves"][key]["white"] += mv["white"]
                root["moves"][key]["draws"] += mv["draws"]
                root["moves"][key]["black"] += mv["black"]
        except Exception as e:
            print(f"  Warning: Failed to fetch year {year}: {e}")
            continue

    root["moves"] = list(root["moves"].values())

    # BFS to explore top lines
    frontier = deque([(start_fen, [], 0, 0.0, float('inf'))])
    lines = []
    seen = set([start_fen])

    print(f"Exploring top {N} lines...")

    while frontier and len(lines) < N:
        fen, san_path, depth, score_aggr, min_cnt = frontier.popleft()

        if len(lines) % 100 == 0 and len(lines) > 0:
            print(f"  Found {len(lines)} lines...")

        # Aggregate position across all years
        parent = {"white": 0, "draws": 0, "black": 0, "moves": {}}
        for year in year_list:
            try:
                data = fetch_counts(fen, year, year, moves=40)
                parent["white"] += data["white"]
                parent["draws"] += data["draws"]
                parent["black"] += data["black"]

                for mv in data.get("moves", []):
                    key = mv["san"]
                    if key not in parent["moves"]:
                        parent["moves"][key] = {"san": mv["san"], "uci": mv.get("uci", ""),
                                                "white": 0, "draws": 0, "black": 0}
                    parent["moves"][key]["white"] += mv["white"]
                    parent["moves"][key]["draws"] += mv["draws"]
                    parent["moves"][key]["black"] += mv["black"]
            except:
                continue

        parent["moves"] = list(parent["moves"].values())
        total_parent = parent["white"] + parent["draws"] + parent["black"]

        if depth >= max_depth or total_parent == 0:
            continue

        # Record this line
        lines.append({
            "depth": depth,
            "san_line": " ".join(san_path) if san_path else "(start)",
            "fen": fen,
            "white": parent["white"],
            "draws": parent["draws"],
            "black": parent["black"],
            "total": total_parent
        })

        # Threshold by depth
        thresh = max(int(M0 * (decay ** depth)), Mmin)
        kids = [mv for mv in children_sorted_by_info(parent, parent["moves"])
                if (mv["white"] + mv["draws"] + mv["black"]) >= thresh]

        for mv in kids:
            c = mv["white"] + mv["draws"] + mv["black"]
            child_fen = mv.get("fen", "")  # API sometimes provides child FEN

            if not child_fen or child_fen in seen:
                continue

            seen.add(child_fen)
            new_path = san_path + [mv["san"]]
            new_score = score_aggr + math.log(c + 1)
            new_min = min(min_cnt, c)

            frontier.append((child_fen, new_path, depth + 1, new_score, new_min))

    print(f"Collected {len(lines)} lines")
    return lines


def main():
    output_dir = Path(__file__).parent.parent / "output"

    # Define even and odd years from 1952 to 2024
    even_years = list(range(1952, 2025, 2))  # 1952, 1954, ..., 2024
    odd_years = list(range(1953, 2025, 2))   # 1953, 1955, ..., 2023

    print("=" * 80)
    print("FETCHING EVEN YEARS DATA")
    print("=" * 80)
    even_lines = aggregate_years(even_years, N=1000)

    # Save even years data
    even_file = output_dir / "masters_lines_even_years.csv"
    with open(even_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["source", "period", "speed", "rating_bucket",
                                                "depth", "san_line", "final_fen", "white",
                                                "draws", "black", "total", "min_node_count",
                                                "score_sumlog"])
        writer.writeheader()
        for line in even_lines:
            writer.writerow({
                "source": "masters",
                "period": "1952-2024-even",
                "speed": "",
                "rating_bucket": "",
                "depth": line["depth"],
                "san_line": line["san_line"],
                "final_fen": line["fen"],
                "white": line["white"],
                "draws": line["draws"],
                "black": line["black"],
                "total": line["total"],
                "min_node_count": line["total"],
                "score_sumlog": 0.0
            })

    print(f"\nSaved even years data to {even_file}")

    print("\n" + "=" * 80)
    print("FETCHING ODD YEARS DATA")
    print("=" * 80)
    odd_lines = aggregate_years(odd_years, N=1000)

    # Save odd years data
    odd_file = output_dir / "masters_lines_odd_years.csv"
    with open(odd_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["source", "period", "speed", "rating_bucket",
                                                "depth", "san_line", "final_fen", "white",
                                                "draws", "black", "total", "min_node_count",
                                                "score_sumlog"])
        writer.writeheader()
        for line in odd_lines:
            writer.writerow({
                "source": "masters",
                "period": "1953-2023-odd",
                "speed": "",
                "rating_bucket": "",
                "depth": line["depth"],
                "san_line": line["san_line"],
                "final_fen": line["fen"],
                "white": line["white"],
                "draws": line["draws"],
                "black": line["black"],
                "total": line["total"],
                "min_node_count": line["total"],
                "score_sumlog": 0.0
            })

    print(f"\nSaved odd years data to {odd_file}")
    print("\n" + "=" * 80)
    print("DONE! Now run:")
    print(f"  python scripts/plot_transposition_scatter.py {even_file} {odd_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
