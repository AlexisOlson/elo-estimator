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

## Notes

- Dependencies are listed in `requirements.txt`. After updating, re-run the setup script.
- The `analyze_pgn.py` script requires lc0 to be built and a network file present in the `networks/` directory.
- Use `--help` flag with any script for detailed usage information.
