#!/usr/bin/env python3
"""
Analyze outliers in period comparison - positions with biggest WDL changes.
"""

import csv
import sys
import argparse
from pathlib import Path
from collections import defaultdict


def normalize_fen(fen):
    """Normalize FEN by removing halfmove clock and fullmove number."""
    parts = fen.split()
    if len(parts) >= 4:
        return ' '.join(parts[:4])
    return fen


def main():
    parser = argparse.ArgumentParser(description="Analyze outlier positions with biggest WDL changes")
    parser.add_argument('input_file', nargs='?', default="output/merged_period_a_b.csv",
                        help='Input CSV file (default: output/merged_period_a_b.csv)')
    parser.add_argument('--min-total-games', type=int, default=3000,
                        help='Minimum total games across both periods (default: 3000)')

    args = parser.parse_args()
    input_file = args.input_file
    min_total_games = args.min_total_games

    print(f"Analyzing outliers in {input_file}...")
    print(f"Filtering to positions with >={min_total_games:,} total games\n")

    # Group by normalized FEN
    fen_data = defaultdict(list)

    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fen = normalize_fen(row['final_fen'])
            white = int(row['white'])
            draws = int(row['draws'])
            black = int(row['black'])
            total = int(row['total'])

            if total == 0:
                continue

            fen_data[fen].append({
                'period': row['period'],
                'san_line': row['san_line'],
                'white_pct': 100 * white / total,
                'draws_pct': 100 * draws / total,
                'black_pct': 100 * black / total,
                'total': total
            })

    # Find positions appearing in both periods
    comparisons = []
    filtered_out = 0

    for fen, occurrences in fen_data.items():
        if len(occurrences) != 2:
            continue

        # Sort by period to ensure consistent ordering
        occurrences.sort(key=lambda x: x['period'])
        period_a, period_b = occurrences

        total_games = period_a['total'] + period_b['total']

        # Filter by minimum total games
        if total_games < min_total_games:
            filtered_out += 1
            continue

        white_diff = abs(period_b['white_pct'] - period_a['white_pct'])
        draws_diff = abs(period_b['draws_pct'] - period_a['draws_pct'])
        black_diff = abs(period_b['black_pct'] - period_a['black_pct'])

        comparisons.append({
            'fen': fen,
            'period_a': period_a,
            'period_b': period_b,
            'total_games': total_games,
            'white_diff': white_diff,
            'draws_diff': draws_diff,
            'black_diff': black_diff,
            'max_diff': max(white_diff, draws_diff, black_diff)
        })

    all_positions = len(comparisons) + filtered_out
    print(f"Found {all_positions} positions appearing in both periods")
    print(f"Filtered to {len(comparisons)} positions with >= {min_total_games:,} total games")
    print(f"({filtered_out} positions excluded due to low game count)\n")

    # Sort by maximum difference
    comparisons.sort(key=lambda x: x['max_diff'], reverse=True)

    print("=" * 100)
    print("TOP 20 OUTLIERS - BIGGEST WDL CHANGES BETWEEN PERIODS")
    print("=" * 100)

    for i, comp in enumerate(comparisons[:20], 1):
        pa = comp['period_a']
        pb = comp['period_b']

        print(f"\n{i}. {pa['san_line']}")
        print(f"   Period A ({pa['period']}): W={pa['white_pct']:5.1f}% D={pa['draws_pct']:5.1f}% L={pa['black_pct']:5.1f}% (n={pa['total']:,})")
        print(f"   Period B ({pb['period']}): W={pb['white_pct']:5.1f}% D={pb['draws_pct']:5.1f}% L={pb['black_pct']:5.1f}% (n={pb['total']:,})")
        print(f"   Changes: dW={comp['white_diff']:+5.1f}pp  dD={comp['draws_diff']:+5.1f}pp  dL={comp['black_diff']:+5.1f}pp")

    # Analyze by category
    print("\n" + "=" * 100)
    print("OUTLIERS BY CATEGORY")
    print("=" * 100)

    # Sort by white win change
    comparisons.sort(key=lambda x: x['period_b']['white_pct'] - x['period_a']['white_pct'], reverse=True)
    print("\nTOP 5: Biggest increase in White wins")
    for i, comp in enumerate(comparisons[:5], 1):
        pa = comp['period_a']
        pb = comp['period_b']
        change = pb['white_pct'] - pa['white_pct']
        print(f"  {i}. {pa['san_line'][:60]}")
        print(f"     {pa['white_pct']:.1f}% -> {pb['white_pct']:.1f}% (+{change:.1f}pp)")

    print("\nTOP 5: Biggest decrease in White wins")
    for i, comp in enumerate(reversed(comparisons[-5:]), 1):
        pa = comp['period_a']
        pb = comp['period_b']
        change = pb['white_pct'] - pa['white_pct']
        print(f"  {i}. {pa['san_line'][:60]}")
        print(f"     {pa['white_pct']:.1f}% -> {pb['white_pct']:.1f}% ({change:.1f}pp)")

    # Sort by draw change
    comparisons.sort(key=lambda x: x['period_b']['draws_pct'] - x['period_a']['draws_pct'], reverse=True)
    print("\nTOP 5: Biggest increase in Draws")
    for i, comp in enumerate(comparisons[:5], 1):
        pa = comp['period_a']
        pb = comp['period_b']
        change = pb['draws_pct'] - pa['draws_pct']
        print(f"  {i}. {pa['san_line'][:60]}")
        print(f"     {pa['draws_pct']:.1f}% -> {pb['draws_pct']:.1f}% (+{change:.1f}pp)")

    print("\nTOP 5: Biggest decrease in Draws")
    for i, comp in enumerate(reversed(comparisons[-5:]), 1):
        pa = comp['period_a']
        pb = comp['period_b']
        change = pb['draws_pct'] - pa['draws_pct']
        print(f"  {i}. {pa['san_line'][:60]}")
        print(f"     {pa['draws_pct']:.1f}% -> {pb['draws_pct']:.1f}% ({change:.1f}pp)")


if __name__ == "__main__":
    main()
