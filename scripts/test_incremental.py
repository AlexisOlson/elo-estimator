"""Test incremental CSV writing with constant threshold"""

import sys
import os
import time

# Import from masters_crawler
sys.path.insert(0, os.path.dirname(__file__))
from masters_crawler import crawl_masters_by_year

if __name__ == "__main__":
    print("="*60)
    print("TESTING Incremental CSV Writing")
    print("="*60)
    print("Config: 2023-2024, min_games=300, max_depth=6")
    print("Watch the CSV file grow as lines are discovered!")
    print()

    output_file = "output/test_incremental.csv"
    print(f"Writing to: {output_file}")
    print("You can open this file in another program while it runs")
    print()

    start_time = time.time()

    # Test with smaller threshold for reasonable runtime
    crawl_masters_by_year(
        years=[(2023, 2024)],
        output_file=output_file,
        N=None,               # Keep all lines found
        min_games=300,        # Moderate threshold
        max_depth=6,          # Limit depth for testing
        max_nodes_per_bucket=None  # Exhaustive within depth limit
    )

    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.1f} seconds")
    print(f"Check {output_file} for results")
