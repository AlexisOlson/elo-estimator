#!/usr/bin/env python3
"""
Merge two period datasets and create transposition scatter plot.
"""

import sys
import csv
from pathlib import Path
import subprocess


def merge_csvs(file1, file2, output_file):
    """Merge two CSV files into one."""
    print(f"Merging {file1} and {file2} into {output_file}...")

    with open(output_file, 'w', newline='', encoding='utf-8') as fout:
        writer = None
        rows_written = 0

        for input_file in [file1, file2]:
            with open(input_file, 'r', encoding='utf-8') as fin:
                reader = csv.DictReader(fin)

                if writer is None:
                    writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
                    writer.writeheader()

                for row in reader:
                    writer.writerow(row)
                    rows_written += 1

    print(f"Wrote {rows_written} rows to {output_file}")
    return output_file


def main():
    if len(sys.argv) != 3:
        print("Usage: python merge_and_plot.py <file1.csv> <file2.csv>")
        sys.exit(1)

    file1 = Path(sys.argv[1])
    file2 = Path(sys.argv[2])

    if not file1.exists():
        print(f"Error: {file1} not found")
        sys.exit(1)

    if not file2.exists():
        print(f"Error: {file2} not found")
        sys.exit(1)

    # Create merged filename
    output_file = file1.parent / f"merged_{file1.stem}_{file2.stem}.csv"

    # Merge the files
    merged_file = merge_csvs(file1, file2, output_file)

    # Run the plot script
    print(f"\nGenerating transposition scatter plot...")
    plot_script = Path(__file__).parent / "plot_transposition_scatter.py"

    result = subprocess.run(
        ["python", str(plot_script), str(merged_file)],
        capture_output=False
    )

    if result.returncode == 0:
        print("\nSuccess! Check the output directory for the plot.")
    else:
        print(f"\nError running plot script (exit code {result.returncode})")
        sys.exit(1)


if __name__ == "__main__":
    main()
