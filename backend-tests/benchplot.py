#!/usr/bin/env python3
# benchplot
#
# Usage:
#   python benchplot bench_output.txt -o bench_chart.png -c bench_data.csv
#
# Notes:
# - Parses lines like: "Benchmark batch size 22 ... throughput 1626.43 nps."
# - Writes a CSV (size,nps) and a PNG chart.
# - If duplicate sizes occur, keeps the MAX nps seen for that size (sensible for noisy runs).
# - Optional flags:
#     --agg last|max|mean   (default: max)
#     --title "Custom title"


import argparse
import csv
import re
import os
from collections import defaultdict
import matplotlib.pyplot as plt


PATTERN = re.compile(
    r"Benchmark\s+batch\s+size\s+(\d+).*?throughput\s+([\d.]+)\s*nps",
    re.IGNORECASE | re.DOTALL,
)

# Metadata regexes
RE_WEIGHT = re.compile(r"Loading weights file from: (?:networks\\)?([\w.-]+)")
RE_BACKEND = re.compile(r"Switching to \[([^\]]+)\]")
RE_CUDA = re.compile(r"CUDA Runtime version: ([\d.]+)")
RE_GPU = re.compile(r"GPU: (.+)")
def extract_metadata(text):
    weightfile = None
    backend = None
    cuda = None
    gpu = None
    m = RE_WEIGHT.search(text)
    if m:
        weightfile = m.group(1)
    m = RE_BACKEND.search(text)
    if m:
        backend = m.group(1)
    m = RE_CUDA.search(text)
    if m:
        cuda = m.group(1)
    m = RE_GPU.search(text)
    if m:
        raw_gpu = m.group(1)
        # Drop anything before GTX, RTX, RX, or the first digit
        import re as _re
        m_model = _re.search(r'(GTX.*|RTX.*|RX.*)', raw_gpu, _re.IGNORECASE)
        if m_model:
            gpu = m_model.group(1)
        else:
            m_digit = _re.search(r'(\d.*)', raw_gpu)
            gpu = m_digit.group(1) if m_digit else raw_gpu
    return weightfile, backend, cuda, gpu

def parse_args():
    ap = argparse.ArgumentParser(description="Plot Lc0 backendbench throughput vs minibatch size.")
    ap.add_argument("input", help="Path to text file containing raw Lc0 backendbench output")
    ap.add_argument("-o", "--out-png", default=None, help="Output PNG path (default: based on weights file)")
    ap.add_argument("-c", "--out-csv", default=None, help="Output CSV path (default: based on weights file)")
    ap.add_argument("--agg", choices=["max", "mean", "last"], default="max",
                    help="How to aggregate nps when a batch size appears multiple times")
    ap.add_argument("--title", default="LC0 backendbench: throughput vs minibatch size",
                    help="Chart title")
    return ap.parse_args()

def aggregate(values, mode):
    if mode == "last":
        return values[-1]
    if mode == "mean":
        return sum(values) / len(values)
    # default 'max'
    return max(values)

def extract_size_nps(text, agg_mode="max"):
    buckets = defaultdict(list)
    for m in PATTERN.finditer(text):
        size = int(m.group(1))
        nps = float(m.group(2))
        buckets[size].append(nps)
    if not buckets:
        raise ValueError("No 'Benchmark batch size ... throughput ... nps' lines found.")
    sizes = sorted(buckets.keys())
    nps_vals = [aggregate(buckets[s], agg_mode) for s in sizes]
    return sizes, nps_vals

def write_csv(path, sizes, nps_vals):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["size", "nps"])
        for s, n in zip(sizes, nps_vals):
            w.writerow([s, f"{n:.6f}"])

def plot(sizes, nps_vals, out_png, title, legend_lines=None):
    # Find peak
    peak_idx = max(range(len(nps_vals)), key=lambda i: nps_vals[i])
    peak_size = sizes[peak_idx]
    peak_nps = nps_vals[peak_idx]

    # Plot
    plt.figure(figsize=(8, 5))
    nps_vals_knps = [v / 1000.0 for v in nps_vals]
    # Thinner line, smaller marker
    plt.plot(sizes, nps_vals_knps, marker="o", markersize=3.5, linewidth=1, color="#2066b2")
    plt.xlabel("Minibatch size")
    plt.ylabel("Throughput (knps)")
    plt.title(title)
    # Add subtle horizontal gridlines
    plt.gca().yaxis.grid(True, which='major', color='gray', alpha=0.3, linestyle='-')
    plt.gca().set_axisbelow(True)
    # Add minor x-ticks at intervals of 10 or 25
    import matplotlib.ticker as mticker
    x_range = max(sizes) - min(sizes)
    interval = 10 if x_range <= 200 else 25
    plt.gca().xaxis.set_minor_locator(mticker.MultipleLocator(interval))
    plt.gca().tick_params(axis='x', which='minor', length=3, color='gray')

    # Mark the peak
    plt.axvline(peak_size, linestyle="--", alpha=0.5, color="#e07a00")
    # Place annotation to the left of the peak to avoid overlapping the data and title
    label_x = peak_size - max(4, int(0.08*len(sizes)))
    label_x = max(label_x, min(sizes))  # Don't go below min batch size
    label_y = (peak_nps/1000.0)
    plt.annotate(
        f"peak @ {peak_size}: {peak_nps/1000:.1f} knps",
        xy=(peak_size, peak_nps/1000.0),
        xytext=(label_x, label_y),
        arrowprops=dict(arrowstyle="->", color="#e07a00", lw=1.5),
        ha='right', va='center',
        fontsize=11, fontweight='bold', color="#e07a00",
        bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#e07a00', lw=1, alpha=0.9)
    )


    # Add metadata as a text box (not a legend), left-align keys, right-align values
    if legend_lines:
        # Parse keys and values
        pairs = []
        for line in legend_lines:
            if ':' in line:
                k, v = line.split(':', 1)
                pairs.append((k.strip(), v.strip()))
        # Find max key length for alignment
        key_width = max(len(k) for k, v in pairs)
        val_width = max(len(v) for k, v in pairs)
        # Build aligned lines
        textstr = "\n".join(f"{k.ljust(key_width)}: {v.rjust(val_width)}" for k, v in pairs)
        plt.gca().text(
            0.98, 0.02, textstr,
            transform=plt.gca().transAxes,
            fontsize=10,
            family='monospace',
            verticalalignment='bottom',
            horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray')
        )

    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    print(f"Wrote PNG: {out_png}")
    print(f"Peak throughput: size={peak_size}, knps={peak_nps/1000:.2f}")


def main():
    args = parse_args()
    with open(args.input, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # Extract metadata


    weightfile, backend, cuda, gpu = extract_metadata(text)
    # Use input file stem for output filenames
    input_stem = os.path.splitext(os.path.basename(args.input))[0]
    # Output folders
    csv_dir = os.path.join(os.path.dirname(__file__), "output-csv")
    png_dir = os.path.join(os.path.dirname(__file__), "output-png")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(png_dir, exist_ok=True)
    out_csv = args.out_csv or os.path.join(csv_dir, f"{input_stem}.csv")
    out_png = args.out_png or os.path.join(png_dir, f"{input_stem}.png")

    # Print metadata
    print("Metadata:")
    print(f"  weights: {weightfile}")
    print(f"  backend: {backend}")
    print(f"  CUDA:    {cuda}")
    print(f"  GPU:     {gpu}")

    sizes, nps_vals = extract_size_nps(text, agg_mode=args.agg)
    write_csv(out_csv, sizes, nps_vals)
    print(f"Wrote CSV: {out_csv}  ({len(sizes)} rows)")

    # Legend for PNG
    legend_lines = [
        f"weights: {weightfile}",
        f"backend: {backend}",
        f"CUDA:    {cuda}",
        f"GPU:     {gpu}"
    ]
    plot(sizes, nps_vals, out_png, args.title, legend_lines=legend_lines)

if __name__ == "__main__":
    main()
