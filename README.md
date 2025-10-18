# Chess Elo Estimator via Move Quality Analysis

A system for estimating player chess strength by analyzing move quality using Leela Chess Zero engine evaluations. Created to calibrate historical chess ratings (Chessmetrics) to modern FIDE Elo standards.

## Project Background

### The Problem
Historical rating systems (Chessmetrics, Elo's original calculations) can determine *relative* rankings but lack absolute calibration. When we say Morphy was rated 2690 or Capablanca 2725, these numbers are somewhat arbitrary - they preserve strength differences but the overall magnitude is uncertain.

### The Solution
Modern chess engines provide an "absolute" measure of move quality. By training a model on games with known FIDE ratings and their engine evaluations, we can:
1. Learn the relationship between move quality and playing strength
2. Apply this model to historical games to estimate absolute Elo in modern terms
3. Calibrate entire historical rating lists to appropriate magnitudes

### Why Leela Chess Zero?
Per GM Larry Kaufman's advice, Leela's evaluations measure *practical chances* against strong opposition, while Stockfish optimizes for *perfect play*. Since we're modeling human performance, Leela's evaluation philosophy better matches human decision-making patterns (fewer forced positions evaluated as 0.00).

## Prior Research

This builds on established work in chess Elo estimation:
- **Regan & Haworth (2011)**: "Intrinsic Chess Ratings" - foundational statistical framework using Rybka
- **Kaggle (2013)**: "Finding Elo" competition - established centipawn loss baselines
- **Omori & Tadepalli (2024)**: CNN-LSTM achieving 182 MAE - current state-of-the-art

Key insight: Modern deep learning outperforms hand-crafted features, but no comprehensive system exists using current engines (Stockfish 17, Leela with BT4 networks).

## How It Works

### Phase 1: Data Collection
1. Run Leela Chess Zero on 40,000 modern games (late 2024/early 2025) with known FIDE ratings
2. For each position (~3.5M total), extract:
   - Win/Draw/Loss probabilities
   - Top 5-10 candidate moves with statistics (N, P, Q, WDL values)
   - Move actually played
   - Player ratings from PGN headers

### Phase 2: Model Training
1. Train ML model (gradient boosted trees, neural network, or ensemble) to predict player Elo from move quality patterns
2. Features: move rankings, evaluation differences, position complexity, game phase
3. Target: Human FIDE Elo rating

### Phase 3: Historical Calibration
1. Apply trained model to 23,000 historical elite games (1843-2005)
2. Estimate average playing strength of top-20 players per era
3. Calibrate Chessmetrics rating lists to appropriate absolute magnitudes

## Technical Architecture

### Modified Leela Chess Zero Engine
Based on [borg's action-replay-san branch](https://github.com/borg323/lc0/tree/action-replay-san):
- Uses `selfplay` mode with `--replay-pgn` to process games in parallel
- **Key Modification**: Export evaluation data per position in structured format
- **Fixed nodes** (not time) for consistency: `--visits=10000` per position
- Outputs JSON Lines format for streaming/append operations

### Evaluation Output Format
```json
{
  "game_id": "training_001",
  "ply": 12,
  "fen": "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -",
  "white_elo": 2700,
  "black_elo": 2650,
  "to_move": "white",
  "played_move": "Nc3",
  "candidates": [
    {"move": "Nc3", "n": 8234, "w": 0.48, "d": 0.35, "l": 0.17, "p": 0.42, "q": 0.395},
    {"move": "d4", "n": 1566, "w": 0.46, "d": 0.36, "l": 0.18, "p": 0.18, "q": 0.380},
    {"move": "Bb5", "n": 200, "w": 0.45, "d": 0.35, "l": 0.20, "p": 0.08, "q": 0.375}
  ]
}
```

### Processing Pipeline
```
Raw PGN → Split into batches → Modified lc0 analysis → JSONL output → 
Consolidate → Training dataset → ML model → Historical game analysis
```

## Dataset

### Training Data
- **Source**: Lichess/FIDE standard rated games
- **Size**: ~40,000 games (~3.5M positions)
- **Period**: Late 2024 - Early 2025
- **Format**: PGN with player names and FIDE Elo ratings
- **Target time**: ~4 days processing (0.1s per position with 10K nodes)

### Historical Data (Target Application)
- **Source**: Chessmetrics database
- **Size**: ~23,000 elite games
- **Period**: 1843-2005
- **Players**: Top-20 per historical era for calibration

## Project Structure

```
elo-estimator/
├── lc0/                           # Modified Leela Chess Zero (forked)
│   ├── src/                       # C++ source code
│   └── build/                     # Compiled binaries
├── networks/                      # Leela neural network weights
│   └── 791556.pb.gz              # Current network in use
├── pgn-data/
│   ├── raw/                       # Original training games
│   └── samples/                   # Small test files for development
├── output/                        # Analysis output files
├── scripts/                       # Python processing scripts
│   ├── parse_lc0_output.py       # Parse lc0 verbose output to JSONL
│   ├── requirements.txt          # Python dependencies
│   └── venv/                      # Python virtual environment
└── docs/                          # Documentation
    ├── PROJECT_BRIEF.md          # Project overview
    ├── output_format.json        # Target output schema
    └── sample_input.pgn          # Sample PGN for testing
```

## Current Status

- [x] Project structure established
- [x] Repository forked and cloned
- [x] lc0 builds successfully
- [x] Test on sample PGN (10 games)
- [x] Parse lc0 verbose output to JSONL format
- [ ] Modify lc0 to export evaluation data directly
- [ ] Validate output format matches training needs
- [ ] Process first 100-game batch
- [ ] Process full 40K training set
- [ ] Train Elo estimation model
- [ ] Apply to historical games

## Getting Started

### Prerequisites

**Hardware**:
- CUDA-capable NVIDIA GPU (required for reasonable performance)
- 16GB+ RAM recommended
- 100GB+ disk space for networks, data, and output

**Software**:
- CUDA Toolkit 11.x or 12.x
- CMake 3.14+
- C++ compiler (MSVC 2019+, GCC 9+, or Clang)
- Python 3.8+
- Git

### Installation

```bash
# Clone the project
git clone https://github.com/AlexisOlson/elo-estimator.git
cd elo-estimator

# The lc0 submodule is already included
cd lc0
git checkout elo-estimator  # Our feature branch

# Build lc0
mkdir build && cd build
cmake .. -DCUDA=on
cmake --build . -j8

# Set up Python environment
cd ../../scripts
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Download a Leela network (if not already present)
cd ../networks
# Network 791556.pb.gz should be placed here
```

### Quick Test

```bash
# Test on sample data
cd lc0/build
./lc0 selfplay \
  --replay-pgn=../../pgn-data/samples/first10.pgn \
  --visits=10000 \
  -w ../../networks/791556.pb.gz
```

## Configuration

### Network Selection
- **Small** (128x10 blocks): Fast testing, lower accuracy
- **Medium** (256x20 blocks): **Recommended** - good speed/accuracy balance
- **Large** (768x15 blocks): Highest accuracy, much slower

### Node Count Selection
Use `--visits=N` for fixed node evaluation:
- **1,000 nodes**: Ultra-fast, rough estimates
- **10,000 nodes**: **Recommended** - good accuracy at ~0.1s/position
- **100,000 nodes**: Very accurate, ~10x slower

Trade-off: More nodes = better evaluation but longer runtime

## Performance Targets

- **Throughput**: ~10 positions/second (10K nodes/position on RTX 3080)
- **Full dataset**: ~4 days for 40K games (3.5M positions)
- **Batch size**: 1,000 games per batch (manageable chunks)
- **Parallelism**: lc0 selfplay mode handles GPU efficiently

## Key Technical Decisions

1. **Fixed nodes vs time**: Ensures consistent evaluation depth across positions
2. **Leela over Stockfish**: Practical chances vs perfect play evaluation
3. **Candidate moves**: Captures decision-making complexity, not just position eval
4. **JSON Lines format**: Streaming-friendly, easy to process incrementally
5. **Batch processing**: Fault tolerance, progress tracking, resumable

## References

### Code & Tools
- [lc0 (Leela Chess Zero)](https://github.com/LeelaChessZero/lc0)
- [borg's action-replay-san branch](https://github.com/borg323/lc0/tree/action-replay-san)
- [python-chess](https://python-chess.readthedocs.io/)
- [Leela Networks](https://training.lczero.org/networks/)

### Research Papers
- Regan & Haworth (2011). "Intrinsic Chess Ratings." *AAAI*. [PDF](https://cdn.aaai.org/ojs/7951/7951-13-11479-1-2-20201228.pdf)
- Omori & Tadepalli (2024). "Chess Rating Estimation from Moves and Clock Times Using a CNN-LSTM." [arXiv:2409.11506](https://arxiv.org/abs/2409.11506)
- Kaggle (2013). "Finding Elo" competition. [Link](https://www.kaggle.com/competitions/finding-elo/overview)

### Related Projects
- [Chessmetrics](http://www.chessmetrics.com/) - Historical rating system by Jeff Sonas
- [RatingNet](https://github.com/AstroBoy1/RatingNet) - CNN-LSTM implementation
- [Ken Regan's work](https://cse.buffalo.edu/~regan/) - Anti-cheating detection

## Attribution

This project builds on decades of chess rating research and is specifically designed to support historical rating calibration for the Chessmetrics system.

**Core Concept**: Jeff Sonas (Chessmetrics creator)  
**Engine Base**: Leela Chess Zero team  
**Action-replay code**: borg (lc0 contributor)  
**Implementation**: [Your Name]

## License

GPL v3.0

---

**Note**: This is research software under active development. Evaluation parameters and methods may be refined based on empirical results.