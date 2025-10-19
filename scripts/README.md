# Scripts README

This folder contains helper scripts and utilities for the project.

## IMPORTANT: Command-Line Usage Rules

**DO NOT modify `config/lc0_config.json` for temporary changes or testing!**

The config file is for persistent defaults. For experiments, testing, or one-off runs, **always use command-line overrides**.

### Critical Syntax Rules

1. **Positional arguments FIRST** (not flags) for input/output files:
   ```bash
   python scripts/analyze_pgn.py <pgn_file> <output_file> [options]
   ```

2. **Wrong flags that will fail:**
   - `--pgn` (doesn't exist)
   - `--output` (doesn't exist)
   - `--nodes` (use `--search.nodes=N` instead)

3. **Correct override syntax (after positional args):**
   - `--search.nodes=100` (search parameters)
   - `--lc0.threads=4` (lc0 options)
   - `--set max_candidates=5` (config overrides)

## Files

- `setup_venv.ps1` - Creates a Python virtual environment and installs dependencies (Windows/PowerShell)
- `analyze_pgn.py` - Main analysis script that processes PGN files with lc0 engine evaluations
- `requirements.txt` - Python package dependencies

## Quick Start (Windows PowerShell)

### 1. Create and activate virtual environment

```powershell
cd elo-estimator
.\scripts\setup_venv.ps1
.\.venv\Scripts\Activate.ps1
```

### 2. Analyze a PGN file

```powershell
# Basic usage (uses config file defaults: 1000 nodes)
python scripts/analyze_pgn.py `
  pgn-data/samples/first10.pgn `
  output/analysis.json `
  --config config/lc0_config.json

# Quick test with fewer nodes (100 nodes)
python scripts/analyze_pgn.py `
  pgn-data/samples/single.pgn `
  output/single_test_100nodes.json `
  --config config/lc0_config.json `
  --search.nodes=100
```

## Quick Start (Linux/Mac)

```bash
cd elo-estimator
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt

# Basic usage (uses config file defaults: 1000 nodes)
python scripts/analyze_pgn.py \
  pgn-data/samples/first10.pgn \
  output/analysis.json \
  --config config/lc0_config.json

# Quick test with fewer nodes (100 nodes)
python scripts/analyze_pgn.py \
  pgn-data/samples/single.pgn \
  output/single_test_100nodes.json \
  --config config/lc0_config.json \
  --search.nodes=100
```

## Command-Line Options

The `analyze_pgn.py` script provides flexible command-line overrides:

### Basic Usage
```bash
python scripts/analyze_pgn.py <pgn_file> <output_file> [options]
```

### Search Parameter Overrides
```bash
# Override number of nodes (visits)
python scripts/analyze_pgn.py game.pgn output.json --search.nodes=50

# Override search time (milliseconds)
python scripts/analyze_pgn.py game.pgn output.json --search.movetime=1000

# Override search depth
python scripts/analyze_pgn.py game.pgn output.json --search.depth=20
```

### lc0 Engine Options
```bash
# Set individual lc0 options
python scripts/analyze_pgn.py game.pgn output.json --lc0.backend=cuda-fp16 --lc0.threads=4

# Or use --lc0-args for multiple options
python scripts/analyze_pgn.py game.pgn output.json --lc0-args backend=cuda-fp16 threads=4
```

### General Config Overrides
```bash
# Override any config value
python scripts/analyze_pgn.py game.pgn output.json --set max_candidates=3 --set search.value=100
```

### Combined Examples
```bash
# Quick test: 50 nodes, 3 candidates, 2 threads
python scripts/analyze_pgn.py game.pgn output.json \
  --search.nodes=50 \
  --lc0.threads=2 \
  --set max_candidates=3

# Full analysis: 10K nodes, cuda-fp16 backend
python scripts/analyze_pgn.py game.pgn output.json \
  --search.nodes=10000 \
  --lc0.backend=cuda-fp16
```

### Get Help
```bash
python scripts/analyze_pgn.py --help
```

## Notes

- Dependencies are listed in `requirements.txt`. After updating, re-run the setup script.
- The `analyze_pgn.py` script requires lc0 to be built and a network file present in the `networks/` directory.
- Command-line overrides take precedence over config file values.
- Use `--help` flag with any script for detailed usage information.

---

**Attribution**: This project was almost entirely written by Claude Sonnet 4.5, with Alexis Olson serving as the driver and director.
