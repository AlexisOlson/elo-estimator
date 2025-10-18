# Scripts README

This folder contains helper scripts and utilities for the project.

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
python scripts/analyze_pgn.py `
  --config config/lc0_config.json `
  --pgn pgn-data/samples/first10.pgn `
  --output output/analysis.json
```

## Quick Start (Linux/Mac)

```bash
cd elo-estimator
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt

python scripts/analyze_pgn.py \
  --config config/lc0_config.json \
  --pgn pgn-data/samples/first10.pgn \
  --output output/analysis.json
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
