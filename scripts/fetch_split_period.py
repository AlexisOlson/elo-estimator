#!/usr/bin/env python3
"""
Fetch masters data for two split periods to measure true transposition noise
without temporal drift confounding.
"""

import sys
import csv
import argparse
from pathlib import Path
from lichess_masters import top_lines


def main():
    parser = argparse.ArgumentParser(description="Fetch split period data from Masters database")
    parser.add_argument('--period-a', nargs=2, type=int, metavar=('START', 'END'),
                        default=[2000, 2011], help='Period A year range (default: 2000 2011)')
    parser.add_argument('--period-b', nargs=2, type=int, metavar=('START', 'END'),
                        default=[2012, 2023], help='Period B year range (default: 2012 2023)')
    parser.add_argument('--min-games', type=int, default=1000,
                        help='Minimum games required in at least one period (default: 1000)')
    parser.add_argument('-N', type=int, default=1000,
                        help='Number of lines to fetch (default: 1000)')

    args = parser.parse_args()

    output_dir = Path(__file__).parent.parent / "output"

    # Extract periods
    period_a_start, period_a_end = args.period_a
    period_b_start, period_b_end = args.period_b
    min_games = args.min_games
    N = args.N

    print("=" * 80)
    print(f"FETCHING PERIOD A: {period_a_start}-{period_a_end}")
    print(f"Minimum games threshold: {min_games}")
    print("=" * 80)

    # Open CSV file for streaming writes
    file_a = output_dir / f"masters_lines_{period_a_start}_{period_a_end}.csv"
    lines_written_a = 0

    with open(file_a, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["source", "period", "speed", "rating_bucket",
                                                "depth", "san_line", "final_fen", "white",
                                                "draws", "black", "total", "min_node_count",
                                                "score_sumlog"])
        writer.writeheader()

        # Callback to write lines as they're collected
        def write_line_a(line):
            nonlocal lines_written_a
            if line['total'] >= min_games:
                writer.writerow({
                    "source": "masters",
                    "period": f"{period_a_start}-{period_a_end}",
                    "speed": "",
                    "rating_bucket": "",
                    "depth": line["depth"],
                    "san_line": line["san_line"],
                    "final_fen": line["fen"],
                    "white": line["white"],
                    "draws": line["draws"],
                    "black": line["black"],
                    "total": line["total"],
                    "min_node_count": line["min_node_count"],
                    "score_sumlog": line["score_sumlog"]
                })
                f.flush()  # Flush to disk immediately
                lines_written_a += 1

        # Fetch with streaming callback
        lines_a = top_lines(period_a_start, period_a_end, N=N, M0=500, decay=0.6, Mmin=40, max_depth=20, line_callback=write_line_a)

    print(f"\nSaved Period A to {file_a}")
    print(f"Total lines written: {lines_written_a} (from {len(lines_a)} collected, filtered >= {min_games} games)")

    print("\n" + "=" * 80)
    print(f"FETCHING PERIOD B: {period_b_start}-{period_b_end}")
    print(f"Minimum games threshold: {min_games}")
    print("=" * 80)

    # Open CSV file for streaming writes
    file_b = output_dir / f"masters_lines_{period_b_start}_{period_b_end}.csv"
    lines_written_b = 0

    with open(file_b, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["source", "period", "speed", "rating_bucket",
                                                "depth", "san_line", "final_fen", "white",
                                                "draws", "black", "total", "min_node_count",
                                                "score_sumlog"])
        writer.writeheader()

        # Callback to write lines as they're collected
        def write_line_b(line):
            nonlocal lines_written_b
            if line['total'] >= min_games:
                writer.writerow({
                    "source": "masters",
                    "period": f"{period_b_start}-{period_b_end}",
                    "speed": "",
                    "rating_bucket": "",
                    "depth": line["depth"],
                    "san_line": line["san_line"],
                    "final_fen": line["fen"],
                    "white": line["white"],
                    "draws": line["draws"],
                    "black": line["black"],
                    "total": line["total"],
                    "min_node_count": line["min_node_count"],
                    "score_sumlog": line["score_sumlog"]
                })
                f.flush()  # Flush to disk immediately
                lines_written_b += 1

        # Fetch with streaming callback
        lines_b = top_lines(period_b_start, period_b_end, N=N, M0=500, decay=0.6, Mmin=40, max_depth=20, line_callback=write_line_b)

    print(f"\nSaved Period B to {file_b}")
    print(f"Total lines written: {lines_written_b} (from {len(lines_b)} collected, filtered >= {min_games} games)")

    print("\n" + "=" * 80)
    print("DONE! Now merge and analyze:")
    print(f"  python scripts/merge_and_plot.py {file_a} {file_b}")
    print("=" * 80)


if __name__ == "__main__":
    main()
