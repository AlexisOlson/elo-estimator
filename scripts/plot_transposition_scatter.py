#!/usr/bin/env python3
"""
Create scatter plots comparing WDL values for transpositions.
For each FEN with multiple occurrences, plots the highest-game occurrence
against all other occurrences to visualize noise/consistency.
"""

import sys
import csv
from pathlib import Path
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt


def normalize_fen(fen):
    """
    Normalize FEN by removing halfmove clock and fullmove number.
    These can differ for transpositions due to move order.
    Returns: position + color + castling + en passant
    """
    parts = fen.split()
    if len(parts) >= 4:
        return ' '.join(parts[:4])
    return fen


def has_repetition_pattern(san_line):
    """
    Detect if a move sequence contains obvious repetition patterns.
    Returns True if the line looks like it includes moves being repeated
    (e.g., Ng4 Bc1 Nf6 Be3 Ng4 Bc1 Nf6 Be3...)
    """
    moves = san_line.split()

    # If too short, no meaningful pattern
    if len(moves) < 8:
        return False

    # Look for repeating 2-move, 3-move, or 4-move patterns
    for pattern_len in [2, 3, 4]:
        if len(moves) < pattern_len * 3:
            continue

        # Check if we see the same pattern at least 3 times
        for start in range(len(moves) - pattern_len * 3):
            pattern = tuple(moves[start:start + pattern_len])

            # Count consecutive repetitions
            reps = 1
            pos = start + pattern_len
            while pos + pattern_len <= len(moves):
                next_segment = tuple(moves[pos:pos + pattern_len])
                if next_segment == pattern:
                    reps += 1
                    pos += pattern_len
                else:
                    break

            if reps >= 3:
                return True

    return False


def load_transpositions(csv_path):
    """Load CSV and group by FEN to find transpositions, filtering repetition artifacts."""
    fen_occurrences = defaultdict(list)
    filtered_count = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            san_line = row['san_line']

            # Skip lines with repetition patterns (artifacts from threefold repetition)
            if has_repetition_pattern(san_line):
                filtered_count += 1
                continue

            # Normalize FEN to ignore halfmove clock and fullmove number
            fen = normalize_fen(row['final_fen'])
            white = int(row['white'])
            draws = int(row['draws'])
            black = int(row['black'])
            total = int(row['total'])

            if total == 0:
                continue

            white_pct = 100 * white / total
            draws_pct = 100 * draws / total
            black_pct = 100 * black / total

            fen_occurrences[fen].append({
                'san_line': san_line,
                'depth': int(row['depth']),
                'white_pct': white_pct,
                'draws_pct': draws_pct,
                'black_pct': black_pct,
                'total': total,
            })

    # Keep only FENs with multiple occurrences
    transpositions = {fen: occs for fen, occs in fen_occurrences.items()
                     if len(occs) > 1}

    if filtered_count > 0:
        print(f"Filtered out {filtered_count} lines with repetition patterns")

    return transpositions


def create_comparison_points(transpositions):
    """
    For each FEN, compare the highest-game occurrence against all others.
    Returns arrays of reference values, comparison values, and sample sizes.
    """
    ref_white = []
    ref_draws = []
    ref_black = []

    cmp_white = []
    cmp_draws = []
    cmp_black = []

    n_ref = []  # sample size for reference
    n_cmp = []  # sample size for comparison

    for fen, occurrences in transpositions.items():
        # Find the occurrence with the most games
        reference = max(occurrences, key=lambda x: x['total'])

        # Compare all other occurrences against this reference
        for occ in occurrences:
            if occ is reference:
                continue

            ref_white.append(reference['white_pct'])
            ref_draws.append(reference['draws_pct'])
            ref_black.append(reference['black_pct'])

            cmp_white.append(occ['white_pct'])
            cmp_draws.append(occ['draws_pct'])
            cmp_black.append(occ['black_pct'])

            n_ref.append(reference['total'])
            n_cmp.append(occ['total'])

    return {
        'ref_white': np.array(ref_white),
        'ref_draws': np.array(ref_draws),
        'ref_black': np.array(ref_black),
        'cmp_white': np.array(cmp_white),
        'cmp_draws': np.array(cmp_draws),
        'cmp_black': np.array(cmp_black),
        'n_ref': np.array(n_ref),
        'n_cmp': np.array(n_cmp),
    }


def empirical_std_by_games(diffs, N, n_bins=20):
    """
    Calculate empirical standard deviation of differences as a function of N.
    Bin by N and compute std dev in each bin.
    """
    # Use log bins for N since it spans multiple orders of magnitude
    log_N = np.log10(N + 1)
    min_log, max_log = log_N.min(), log_N.max()

    bins = np.logspace(min_log, max_log, n_bins)
    bin_centers = []
    bin_stds = []

    for i in range(len(bins) - 1):
        mask = (N >= bins[i]) & (N < bins[i + 1])
        if mask.sum() > 5:  # Need at least a few points
            bin_centers.append(np.sqrt(bins[i] * bins[i + 1]))  # Geometric mean
            bin_stds.append(np.std(diffs[mask]))

    return np.array(bin_centers), np.array(bin_stds)


def fit_std_model(N_vals, std_vals):
    """
    Fit model: σ = a/sqrt(N) + b
    where a captures sampling noise and b captures systematic noise.

    Using simple linear regression on transformed variables:
    σ = a/sqrt(N) + b  =>  σ = a*x + b where x = 1/sqrt(N)
    """
    if len(N_vals) < 2:
        # Not enough data, use simple scaling
        mean_std_times_sqrtN = np.mean(std_vals * np.sqrt(N_vals))
        return [mean_std_times_sqrtN, 0.0]

    # Transform: x = 1/sqrt(N), y = σ
    x = 1.0 / np.sqrt(N_vals)
    y = std_vals

    # Linear regression: y = a*x + b
    # Using normal equations: (X^T X)^-1 X^T y
    n = len(x)
    sum_x = np.sum(x)
    sum_y = np.sum(y)
    sum_xx = np.sum(x * x)
    sum_xy = np.sum(x * y)

    # Solve for a and b
    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-10:
        # Degenerate case, use simple scaling
        mean_std_times_sqrtN = np.mean(y * np.sqrt(N_vals))
        return [mean_std_times_sqrtN, 0.0]

    a = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y * sum_xx - sum_x * sum_xy) / denom

    # Ensure reasonable values (positive a, non-negative b)
    a = max(a, 0.1)
    b = max(b, 0.0)

    return [a, b]


def compute_marker_sizes_and_alphas(n_ref, n_cmp,
                                     min_area=5, max_area=800,
                                     area_at_median_N=60,
                                     ink_per_game=0.0006):
    """
    Compute marker sizes and alphas based on sample size.

    Marker area ∝ 1/sqrt(N):
      - Uncertainty scales as 1/sqrt(N)
      - Visual diameter represents uncertainty

    Opacity × Area ∝ N:
      - Each game contributes constant "ink" to the plot
      - This means opacity ∝ N/area ∝ N^(3/2)
    """
    # Use geometric mean of sample sizes
    N = np.sqrt(n_ref * n_cmp)
    N_median = np.nanmedian(N)

    # Marker area inversely proportional to sqrt(N)
    sizes = area_at_median_N * np.sqrt(N_median / N)
    sizes = np.clip(sizes, min_area, max_area)

    # Opacity such that opacity × area ∝ N (constant ink per game)
    alphas = ink_per_game * N / sizes
    alphas = np.clip(alphas, 0.01, 0.7)

    return sizes, alphas


def plot_all_components(data, output_path):
    """Create a three-panel scatter plot for W, D, L components."""

    # Create figure with three subplots side by side
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    components = [
        ('W', data['ref_white'], data['cmp_white'], 'darkorange'),
        ('D', data['ref_draws'], data['cmp_draws'], 'forestgreen'),
        ('L', data['ref_black'], data['cmp_black'], 'darkviolet'),
    ]

    n_ref = data['n_ref']
    n_cmp = data['n_cmp']
    N = np.sqrt(n_ref * n_cmp)  # Geometric mean

    for ax, (name, ref_vals, cmp_vals, color) in zip(axes, components):
        # Calculate empirical differences (in percentage points)
        diffs = cmp_vals - ref_vals

        # Compute empirical std as function of N
        N_bins, std_bins = empirical_std_by_games(diffs, N)

        # Fit model: sigma = a/sqrt(N) + b
        std_params = fit_std_model(N_bins, std_bins)
        a, b = std_params

        # Compute marker sizes and alphas
        sizes, alphas = compute_marker_sizes_and_alphas(n_ref, n_cmp)

        # Print empirical noise model
        print(f"  {name} - Empirical noise: std = {a:.1f}/sqrt(N) + {b:.2f} pp")

        # Convert from percentage to probability (0-1 scale)
        ref_prob = ref_vals / 100.0
        cmp_prob = cmp_vals / 100.0

        # Diagonal line (perfect agreement) - plot first so it's behind the dots
        lims = [0.0, 0.8]
        ax.plot(lims, lims, 'k-', alpha=1.0, linewidth=0.5)

        # Scatter plot with size ∝ variance, alpha such that ink ∝ N
        ax.scatter(ref_prob, cmp_prob,
                  s=sizes,
                  alpha=alphas,
                  color=color,
                  edgecolors='none')

        # Set axis properties
        ax.set_xlim(lims)
        ax.set_ylim(lims)
        ax.set_xlabel(f'Period A {name} (prob)', fontsize=13)
        ax.set_ylabel(f'Period B {name} (prob)', fontsize=13)
        ax.set_title(f'{name}: Period Comparison', fontsize=14, pad=10)
        ax.grid(True, alpha=0.2, linewidth=0.5)
        ax.set_aspect('equal')

        # Calculate and print statistics
        mae = np.mean(np.abs(diffs))
        rmse = np.sqrt(np.mean(diffs**2))
        print(f"       MAE: {mae:.2f} pp, RMSE: {rmse:.2f} pp")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\nSaved: {output_path}")


def main():
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
    else:
        csv_path = Path(__file__).parent.parent / "output" / "masters_lines_1000games.csv"

    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    print(f"Loading transpositions from {csv_path}...")
    transpositions = load_transpositions(csv_path)

    if not transpositions:
        print("No transpositions found!")
        sys.exit(1)

    print(f"Found {len(transpositions)} positions with transpositions")

    print("Creating comparison points...")
    data = create_comparison_points(transpositions)

    print(f"Total comparison points: {len(data['n_ref'])}")

    # Output directory
    output_dir = csv_path.parent
    base_name = csv_path.stem

    # Create combined plot
    print("\nGenerating plot...")
    plot_all_components(data, output_dir / f'{base_name}_transpositions.png')

    print("\nDone!")


if __name__ == "__main__":
    main()