"""Test exhaustive crawling with constant threshold"""

import sys
import os

# Import from masters_crawler
sys.path.insert(0, os.path.dirname(__file__))
from masters_crawler import crawl_masters_by_year
import csv

if __name__ == "__main__":
    print("="*60)
    print("TESTING Exhaustive Mode - Constant Threshold")
    print("="*60)
    print("Config: 2023-2024, min_games=500, max_depth=8 (limited for testing)")
    print("This will find ALL positions with >=500 games up to depth 8")
    print()

    # Test with smaller threshold for reasonable runtime
    results = crawl_masters_by_year(
        years=[(2023, 2024)],
        N=None,               # Keep all lines found
        min_games=500,        # Higher threshold for faster test
        max_depth=8,          # Limit depth for testing
        max_nodes_per_bucket=None  # Exhaustive within depth limit
    )

    # Show results
    if results:
        print(f"\n{'='*60}")
        print(f"SUCCESS: Found {len(results)} positions with >=500 games")
        print(f"{'='*60}")

        # Show depth distribution
        depth_counts = {}
        for row in results:
            d = row['depth']
            depth_counts[d] = depth_counts.get(d, 0) + 1

        print("\nDepth distribution:")
        for depth in sorted(depth_counts.keys()):
            print(f"  Depth {depth}: {depth_counts[depth]} positions")

        print("\nDeepest lines (top 5):")
        deepest = sorted(results, key=lambda x: x['depth'], reverse=True)[:5]
        for i, row in enumerate(deepest, 1):
            print(f"\n{i}. Depth {row['depth']}: {row['san_line']}")
            print(f"   W/D/L: {row['white']}/{row['draws']}/{row['black']} (total: {row['total']})")

        # Write to test output
        output_file = "output/test_exhaustive.csv"
        fieldnames = [
            "source", "period", "speed", "rating_bucket", "depth",
            "san_line", "final_fen", "white", "draws", "black", "total",
            "min_node_count", "score_sumlog"
        ]

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"\nWrote to: {output_file}")
    else:
        print("\nFAILED: No results found!")