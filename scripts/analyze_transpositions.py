#!/usr/bin/env python3
"""
Analyze transpositions in chess position data to assess noise levels.
Finds positions (FENs) that appear multiple times and compares their WDL statistics.
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path


def calculate_percentages(white, draws, black, total):
    """Calculate WDL percentages."""
    if total == 0:
        return 0.0, 0.0, 0.0
    return (
        100 * white / total,
        100 * draws / total,
        100 * black / total
    )


def calculate_variance(values):
    """Calculate variance of a list of values."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance


def analyze_transpositions(input_file):
    """Analyze transpositions in the CSV file."""

    # Dictionary to store all occurrences of each FEN
    # Key: FEN, Value: list of dicts with WDL data
    fen_occurrences = defaultdict(list)

    print(f"Reading data from {input_file}...")

    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fen = row['final_fen']
            white = int(row['white'])
            draws = int(row['draws'])
            black = int(row['black'])
            total = int(row['total'])

            white_pct, draws_pct, black_pct = calculate_percentages(white, draws, black, total)

            fen_occurrences[fen].append({
                'san_line': row['san_line'],
                'depth': int(row['depth']),
                'white': white,
                'draws': draws,
                'black': black,
                'total': total,
                'white_pct': white_pct,
                'draws_pct': draws_pct,
                'black_pct': black_pct,
            })

    # Find transpositions (FENs that appear multiple times)
    transpositions = {fen: occurrences for fen, occurrences in fen_occurrences.items()
                      if len(occurrences) > 1}

    total_positions = len(fen_occurrences)
    total_transpositions = len(transpositions)

    print(f"\n{'='*80}")
    print(f"TRANSPOSITION ANALYSIS SUMMARY")
    print(f"{'='*80}")
    print(f"Total unique positions: {total_positions:,}")
    print(f"Positions with transpositions: {total_transpositions:,}")
    print(f"Transposition rate: {100 * total_transpositions / total_positions:.2f}%")
    print(f"{'='*80}\n")

    if total_transpositions == 0:
        print("No transpositions found in the data.")
        return

    # Analyze noise in transpositions
    white_variances = []
    draws_variances = []
    black_variances = []
    max_white_diff = 0
    max_draws_diff = 0
    max_black_diff = 0
    max_diff_examples = {'white': None, 'draws': None, 'black': None}

    # Sort transpositions by number of occurrences (descending)
    sorted_transpositions = sorted(transpositions.items(),
                                  key=lambda x: len(x[1]),
                                  reverse=True)

    print(f"{'='*80}")
    print(f"TOP TRANSPOSITIONS BY OCCURRENCE COUNT")
    print(f"{'='*80}\n")

    # Show top 10 most frequent transpositions
    for i, (fen, occurrences) in enumerate(sorted_transpositions[:10], 1):
        print(f"\n{i}. FEN: {fen}")
        print(f"   Occurrences: {len(occurrences)}")
        print(f"   Via these move sequences:")

        for occ in occurrences:
            print(f"     - {occ['san_line']:40s} | "
                  f"W:{occ['white_pct']:5.1f}% D:{occ['draws_pct']:5.1f}% B:{occ['black_pct']:5.1f}% "
                  f"(n={occ['total']:,})")

    print(f"\n{'='*80}")
    print(f"NOISE ANALYSIS - WDL VARIANCE IN TRANSPOSITIONS")
    print(f"{'='*80}\n")

    # Calculate variance statistics
    for fen, occurrences in transpositions.items():
        white_pcts = [occ['white_pct'] for occ in occurrences]
        draws_pcts = [occ['draws_pct'] for occ in occurrences]
        black_pcts = [occ['black_pct'] for occ in occurrences]

        white_var = calculate_variance(white_pcts)
        draws_var = calculate_variance(draws_pcts)
        black_var = calculate_variance(black_pcts)

        white_variances.append(white_var)
        draws_variances.append(draws_var)
        black_variances.append(black_var)

        # Track maximum differences
        white_diff = max(white_pcts) - min(white_pcts)
        draws_diff = max(draws_pcts) - min(draws_pcts)
        black_diff = max(black_pcts) - min(black_pcts)

        if white_diff > max_white_diff:
            max_white_diff = white_diff
            max_diff_examples['white'] = (fen, occurrences)

        if draws_diff > max_draws_diff:
            max_draws_diff = draws_diff
            max_diff_examples['draws'] = (fen, occurrences)

        if black_diff > max_black_diff:
            max_black_diff = black_diff
            max_diff_examples['black'] = (fen, occurrences)

    # Calculate average variances
    avg_white_var = sum(white_variances) / len(white_variances)
    avg_draws_var = sum(draws_variances) / len(draws_variances)
    avg_black_var = sum(black_variances) / len(black_variances)

    print(f"Average WDL variance across all transpositions:")
    print(f"  White win %:  {avg_white_var:.4f}")
    print(f"  Draw %:       {avg_draws_var:.4f}")
    print(f"  Black win %:  {avg_black_var:.4f}")

    avg_total_var = (avg_white_var + avg_draws_var + avg_black_var) / 3
    print(f"  Overall avg:  {avg_total_var:.4f}")

    print(f"\nMaximum percentage point differences:")
    print(f"  White win %:  {max_white_diff:.2f} pp")
    print(f"  Draw %:       {max_draws_diff:.2f} pp")
    print(f"  Black win %:  {max_black_diff:.2f} pp")

    # Show examples of highest variance
    print(f"\n{'='*80}")
    print(f"EXAMPLES OF HIGHEST WDL VARIATION")
    print(f"{'='*80}\n")

    for category, label in [('white', 'White Win %'), ('draws', 'Draw %'), ('black', 'Black Win %')]:
        fen, occurrences = max_diff_examples[category]
        print(f"\nHighest variation in {label}:")
        print(f"FEN: {fen}")
        print(f"Occurrences: {len(occurrences)}")
        print(f"Via these move sequences:")

        for occ in occurrences:
            print(f"  - {occ['san_line']:40s} | "
                  f"W:{occ['white_pct']:5.1f}% D:{occ['draws_pct']:5.1f}% B:{occ['black_pct']:5.1f}% "
                  f"(n={occ['total']:,})")

        if category == 'white':
            pcts = [occ['white_pct'] for occ in occurrences]
        elif category == 'draws':
            pcts = [occ['draws_pct'] for occ in occurrences]
        else:
            pcts = [occ['black_pct'] for occ in occurrences]

        print(f"  Range: {min(pcts):.2f}% - {max(pcts):.2f}% (diff: {max(pcts) - min(pcts):.2f} pp)")
        print(f"  Variance: {calculate_variance(pcts):.4f}")


def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = Path(__file__).parent.parent / "output" / "masters_lines_1000games.csv"

    if not Path(input_file).exists():
        print(f"Error: File not found: {input_file}")
        sys.exit(1)

    analyze_transpositions(input_file)


if __name__ == "__main__":
    main()
