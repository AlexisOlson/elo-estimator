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
- **Engine**: Leela Chess Zero (lc0) - C++, CUDA/GPU
- **Base Code**: borg323/lc0 action-replay-san branch
- **Processing**: Python (python-chess, pandas)
- **Input**: PGN format chess games with player ratings
- **Output**: JSON Lines format with evaluations per position

## Dataset
- Training: ~40,000 games (late 2024/early 2025)
- Known FIDE ratings for all players
- ~3.5 million positions to evaluate
- Historical: ~23,000 elite games (1843-2005) for calibration

## Key Modification Needed
borg's action-replay-san already:
✓ Loads PGN files
✓ Evaluates each position with Leela
✓ Processes games in parallel (GPU efficient)
✓ Outputs moves in SAN notation

We need to ADD:
✗ Export evaluation data per position
✗ Include candidate move rankings with statistics
✗ Capture player ratings from PGN headers
✗ Output structured JSON/JSONL format

## Success Criteria
- Process 40K games in reasonable time (~4 days at 0.1s/position)
- Extract: WDL percentages, top 5-10 candidate moves, N/P/Q statistics
- Generate clean training dataset linking move choices to known Elo ratings
- Validate on subset before full-scale processing

## Resources
- lc0 repo: https://github.com/borg323/lc0/tree/action-replay-san
- Leela networks: https://training.lczero.org/networks/
- UCI protocol: http://wbec-ridderkerk.nl/html/UCIProtocol.html

---

**Note**: This project was almost entirely written by Claude Sonnet 4.5, with Alexis Olson serving as the driver and director.