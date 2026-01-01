#!/usr/bin/env python3
"""
Split masters_lines_1000games.csv into two period groups for comparison.
"""

import csv
from pathlib import Path

def main():
    input_file = Path("output/masters_lines_1000games.csv")
    output_a = Path("output/masters_lines_period_a.csv")
    output_b = Path("output/masters_lines_period_b.csv")

    # Define period groups
    # Period A: Earlier modern era (2000-2009)
    # Period B: Recent era (2015-2024)
    period_a_list = ["2000-2004", "2005-2009"]
    period_b_list = ["2015-2019", "2020-2024"]

    print("Splitting masters_lines_1000games.csv by period...")
    print(f"Period A: {', '.join(period_a_list)}")
    print(f"Period B: {', '.join(period_b_list)}")

    count_a = 0
    count_b = 0

    with open(input_file, 'r', encoding='utf-8') as fin:
        reader = csv.DictReader(fin)
        fieldnames = reader.fieldnames

        with open(output_a, 'w', newline='', encoding='utf-8') as fa, \
             open(output_b, 'w', newline='', encoding='utf-8') as fb:

            writer_a = csv.DictWriter(fa, fieldnames=fieldnames)
            writer_b = csv.DictWriter(fb, fieldnames=fieldnames)

            writer_a.writeheader()
            writer_b.writeheader()

            for row in reader:
                period = row['period']

                if period in period_a_list:
                    writer_a.writerow(row)
                    count_a += 1
                elif period in period_b_list:
                    writer_b.writerow(row)
                    count_b += 1

    print(f"\nPeriod A: {count_a} lines -> {output_a}")
    print(f"Period B: {count_b} lines -> {output_b}")

    # Now merge them
    merged_file = Path("output/merged_period_a_b.csv")
    print(f"\nMerging into {merged_file}...")

    with open(merged_file, 'w', newline='', encoding='utf-8') as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()

        for input_path in [output_a, output_b]:
            with open(input_path, 'r', encoding='utf-8') as fin:
                reader = csv.DictReader(fin)
                for row in reader:
                    writer.writerow(row)

    print(f"Total merged: {count_a + count_b} lines")
    print("\nNow run:")
    print(f"  python scripts/plot_transposition_scatter.py {merged_file}")


if __name__ == "__main__":
    main()
