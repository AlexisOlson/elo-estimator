# Chess Elo Estimation from Move Quality

## Project Overview
Predict chess player Elo ratings by analyzing move quality using Leela Chess Zero engine evaluations.

## The Problem
Historical chess rating systems (Chessmetrics, Elo) can't determine absolute rating levels - only relative rankings. We need a way to calibrate historical ratings to modern Elo standards by measuring move quality.

## The Solution
1. Analyze games with known FIDE ratings using Leela Chess Zero
2. Extract position evaluations and candidate move assessments
3. Train ML model: move quality → player Elo
4. Apply to historical games to estimate absolute playing strength

## Technical Stack
- **Engine**: Leela Chess Zero (lc0) – C++, CUDA/GPU
- **Base Code**: lc0 v0.32.0 (unmodified, UCI protocol)
- **Processing**: Python (python-chess, UCI communication)
- **Input**: PGN format chess games with player ratings
- **Output**: JSON format with evaluations per position (schema v1.0)

## Dataset
- Training: ~100,000 games (late 2024/early 2025)
- Known FIDE ratings for all players
- Historical: ~23,000 elite games (1843-2005) for calibration

## Key Capabilities Delivered
- Per-position JSON export with played move + top candidates (rank, visits, policy, Q, U, WDL)
- PGN metadata capture (players, ratings, event info) merged into analysis output
- Configurable search budgets, lc0 overrides, and command-line overrides
- Incremental progress writing for long batches (safe restart)
- Compact JSON formatting for downstream training pipelines

## Command-Line Usage

The config file (`config/lc0_config.json`) is for persistent defaults.
For testing, experiments, or one-off runs, command-line parameters are recommended.

### Correct Command Syntax

The script uses **positional arguments** for PGN input and output files, which must come FIRST:

```bash
python scripts/analyze_pgn.py <pgn_file> <output_file> [options]
```

### Common Examples

**Run with different node count (100 nodes):**
```bash
python scripts/analyze_pgn.py \
  pgn-data/samples/single.pgn \
  output/single_test_100nodes.json \
  --config config/lc0_config.json \
  --search.nodes=100
```

**Run with different thread count:**
```bash
python scripts/analyze_pgn.py \
  pgn-data/samples/first10.pgn \
  output/analysis.json \
  --config config/lc0_config.json \
  --lc0.threads=4
```

**Override multiple settings:**
```bash
python scripts/analyze_pgn.py \
  pgn-data/samples/single.pgn \
  output/test.json \
  --config config/lc0_config.json \
  --search.nodes=50 \
  --lc0.threads=2 \
  --set max_candidates=5
```

## Success Criteria
- Process 100K games in reasonable time
- Extract: WDL percentages, top 10 candidate moves, N/P/Q/U statistics
- Generate clean training dataset linking move choices to known Elo ratings
- Validate on subset before full-scale processing

## Resources
- lc0 repo: https://github.com/LeelaChessZero/lc0
- Leela networks: https://training.lczero.org/networks/
- UCI protocol: http://wbec-ridderkerk.nl/html/UCIProtocol.html

---

**Note**: This project was almost entirely written by Claude Sonnet 4.5, with Alexis Olson serving as the driver and director.