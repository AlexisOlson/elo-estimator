"""Quick test of the masters crawler with minimal parameters"""

import sys
import os

# Import from masters_crawler
sys.path.insert(0, os.path.dirname(__file__))
from masters_crawler import crawl_masters_by_year
import csv

if __name__ == "__main__":
    print("="*60)
    print("TESTING Masters Crawler - Small Sample")
    print("="*60)
    print("Config: 1 year bucket (2023-2024), top 20 lines, max 200 nodes")
    print()

    # Small test parameters
    results = crawl_masters_by_year(
        years=[(2023, 2024)],  # Just one recent year
        N=20,                  # Only top 20 lines
        M0=300,                # Lower threshold for testing
        decay=0.65,
        Mmin=30,
        max_depth=10,          # Shallower depth
        max_nodes_per_bucket=200  # Small exploration budget
    )

    # Show results
    if results:
        print(f"\n{'='*60}")
        print(f"SUCCESS: Found {len(results)} lines")
        print(f"{'='*60}")
        print("\nTop 5 lines:")
        for i, row in enumerate(results[:5], 1):
            print(f"\n{i}. Depth {row['depth']}: {row['san_line']}")
            print(f"   W/D/L: {row['white']}/{row['draws']}/{row['black']} (total: {row['total']})")
            print(f"   Min count: {row['min_node_count']}, Score: {row['score_sumlog']}")

        # Write to test output
        output_file = "output/test_masters_crawler.csv"
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
