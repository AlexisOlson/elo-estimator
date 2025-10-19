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
Based on an action-replay modification of Leela Chess Zero that enables exporting per-position analysis in a structured format:
- Uses `selfplay` mode with `--replay-pgn` to process games in parallel
- **Key Modification**: Export evaluation data per position in structured format
- **Fixed nodes** (not time) for consistency: `--visits=10000` per position
- Outputs JSON Lines format for streaming/append operations

### Evaluation Output Format
```json
{
  "ply": 12,
  "fen": "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -",
  "to_move": "white",
  "total_visits": 10189,
  "visits_on_better": 0,
  "played_move": "Nc3",
  "evaluation": {"rank": 1, "visits": 8234, "policy": 0.42, "q_value": 0.395, "wdl": [480, 350, 170]},
  "candidate_moves": [
    { "move": "Nc3", "rank":  1, "visits": 8234, "policy": 0.42, "q_value": 0.395, "wdl": [480, 350, 170] },
    { "move": "d4 ", "rank":  2, "visits": 1566, "policy": 0.18, "q_value": 0.380, "wdl": [460, 360, 180] },
    { "move": "Bb5", "rank":  3, "visits":  389, "policy": 0.08, "q_value": 0.375, "wdl": [450, 350, 200] }
  ]
}
```
See [docs/output_format.json](docs/output_format.json) for complete field descriptions.

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
├── lc0/                           # Leela Chess Zero engine (git submodule)
│   ├── src/                       # C++ source code
│   └── build/                     # Compiled binaries
├── networks/                      # Leela neural network weights
│   └── 791556.pb.gz              # Example network file
├── pgn-data/
│   ├── raw/                       # Original training games (gitignored)
│   └── samples/                   # Sample PGN files for testing
├── output/                        # Analysis output files
├── scripts/                       # Python processing scripts
│   ├── analyze_pgn.py            # Main PGN analysis script
│   ├── setup_venv.ps1            # Python environment setup (Windows)
│   ├── requirements.txt          # Python dependencies
│   └── README.md                 # Scripts documentation
├── config/                        # Configuration files
│   └── lc0_config.json           # lc0 engine configuration
└── docs/                          # Documentation
    ├── PROJECT_BRIEF.md          # Project overview (brief)
    ├── config_example.md         # Config file structure documentation
    ├── output_format.json        # Output format specification
    └── sample_input.pgn          # Sample PGN data
```

## Current Status

**Development Stage**: Research/Prototype - Currently building analysis infrastructure

✅ **Completed**:
- Project structure established
- lc0 submodule configured (tracking official v0.32.0 release)
- lc0 builds successfully on Windows (MSVC + CUDA)
- Python analysis script (`analyze_pgn.py`) working with UCI protocol
- Sample PGN analysis tested (first 10 games)
- Output format validated with actual lc0 evaluations

🚧 **In Progress**:
- Testing evaluation consistency across different positions
- Performance optimization for batch processing

📋 **Planned**:
- Process larger game batches (100-1000 games)
- Train Elo estimation model (ML component)
- Validate model accuracy on held-out test set
- Apply to historical games for calibration
- Full 40K training dataset processing

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

**1. Clone the Repository**
```bash
git clone https://github.com/AlexisOlson/elo-estimator.git
cd elo-estimator

# Initialize and update the lc0 submodule
git submodule update --init --recursive
```

**2. Build lc0**

The project uses lc0 (Leela Chess Zero) as a git submodule. You need to build it:

*Windows (PowerShell):*
```powershell
cd lc0
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
meson setup build --backend vs2019 --buildtype release -Dgtest=false -Dcudnn=false
meson compile -C build
# Executable will be at: lc0\build\lc0.exe
```

*Linux/Mac:*
```bash
cd lc0
./build.sh
# Executable will be at: lc0/build/lc0
```

**3. Set up Python Environment**

*Windows (PowerShell):*
```powershell
.\scripts\setup_venv.ps1
.\.venv\Scripts\Activate.ps1
```

*Linux/Mac:*
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

**4. Download a Leela Network**

Download a neural network from [Leela Training](https://training.lczero.org/networks/) and place it in the `networks/` directory. 

Recommended: BT4 networks (791556 or similar). The config assumes `networks/791556.pb.gz`.

```bash
# Example (Linux/Mac)
cd networks
wget https://training.lczero.org/get_network?sha=<network_hash> -O 791556.pb.gz
```

### Quick Test

Run the analysis script on sample data to verify everything works:

*Windows (PowerShell):*
```powershell
# Make sure Python venv is activated
.\.venv\Scripts\Activate.ps1

# Run analysis on sample PGN file
python scripts\analyze_pgn.py `
  --config config\lc0_config.json `
  --pgn pgn-data\samples\first10.pgn `
  --output output\test_analysis.json
```

*Linux/Mac:*
```bash
# Make sure Python venv is activated
source .venv/bin/activate

# Run analysis on sample PGN file
python scripts/analyze_pgn.py \
  --config config/lc0_config.json \
  --pgn pgn-data/samples/first10.pgn \
  --output output/test_analysis.json
```

```

Expected: Creates `output/test_analysis.json` with position evaluations from the first 10 games.

### Command-Line Overrides

The `analyze_pgn.py` script supports convenient command-line overrides for common parameters:

**Quick search parameter changes:**
```powershell
# Override nodes (visits) to 50
python scripts\analyze_pgn.py pgn-data\samples\first10.pgn output\quick_test.json --search.nodes=50

# Override search time instead of nodes
python scripts\analyze_pgn.py game.pgn output.json --search.movetime=1000  # 1 second per position
```

**Override lc0 engine options:**
```powershell
# Change backend and threads
python scripts\analyze_pgn.py game.pgn output.json --lc0.backend=cuda-fp16 --lc0.threads=4

# Or use --lc0-args for multiple options
python scripts\analyze_pgn.py game.pgn output.json --lc0-args backend=cuda-fp16 threads=4
```

**Combine multiple overrides:**
```powershell
# Quick analysis: 50 nodes, 3 candidate moves, 2 threads
python scripts\analyze_pgn.py game.pgn output.json --search.nodes=50 --lc0.threads=2 --set max_candidates=3
```

**General config override:**
```powershell
# Override any config value using --set
python scripts\analyze_pgn.py game.pgn output.json --set search.value=100 --set max_candidates=5
```

For complete documentation, run:
```powershell
python scripts\analyze_pgn.py --help
```

## Configuration

For detailed configuration file structure and all available options, see **[docs/config_example.md](docs/config_example.md)**.

### Network Selection
- **Small** (128x10 blocks): Fast testing, lower accuracy
- **Medium** (256x20 blocks): **Recommended** - good speed/accuracy balance
- **Large** (768x15 blocks): Highest accuracy, much slower

### Node Count Selection
Configure via `--search.nodes=N` or in the config file:
- **1,000 nodes**: Ultra-fast, rough estimates
- **10,000 nodes**: **Recommended** - good accuracy at ~0.1s/position
- **100,000 nodes**: Very accurate, ~10x slower
````

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
**Action-replay modification**: community-contributed change to lc0 enabling replay/export functionality  
**Implementation**: Alexis Olson

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

The lc0 engine (included as a submodule) is also licensed under GPL v3.0 by the Leela Chess Zero contributors.

---

**Note**: This is research software under active development. Evaluation parameters and methods may be refined based on empirical results.