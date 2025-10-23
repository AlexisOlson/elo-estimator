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
1. Run Leela Chess Zero on ~100,000 modern games (late 2024/early 2025) with known FIDE ratings
2. For each position, extract:
   - Win/Draw/Loss probabilities
   - Top 5-10 candidate moves with statistics (N, P, Q, WDL values)
   - Move actually played
   - Player ratings from PGN headers

### Phase 2: Model Training
1. Train ML model (gradient boosted trees, neural network, or ensemble) to predict player Elo from move quality patterns
2. Features: move rankings, evaluation differences, position complexity, game phase
3. Target: Human FIDE Elo rating

### Phase 3: Historical Calibration
1. Apply trained model to historical elite games (1843-2005)
2. Estimate average playing strength of top-20 players per era
3. Calibrate Chessmetrics rating lists to appropriate absolute magnitudes

## Technical Architecture

### Leela Chess Zero Integration
The system uses an unmodified Leela Chess Zero engine via UCI protocol:
- **UCI Protocol**: Standard chess engine communication protocol
- **Fixed nodes** (not time) for consistency: configurable per position (default 1000 nodes)
- Python script (`analyze_pgn.py`) orchestrates analysis and captures structured output
- JSON format for analysis results

### Evaluation Output Format
```json
{
  "ply": 1,
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "to_move": "white",
  "total_visits": 123,
  "visits_on_better": 76,
  "played_move": "e4",
  "evaluation": {"rank": 6, "visits": 10, "policy": 0.0725, "q_value": 0.01256, "wdl": [56, 901, 43]},
  "candidate_moves": [
    { "move": "Nf3", "rank": 1, "visits": 19, "policy": 0.1194, "q_value": 0.02891, "wdl": [63, 903, 34] },
    { "move": "d4" , "rank": 2, "visits": 19, "policy": 0.1227, "q_value": 0.02861, "wdl": [63, 903, 34] },
    { "move": "c4" , "rank": 3, "visits": 15, "policy": 0.1063, "q_value": 0.02329, "wdl": [60, 903, 37] }
  ]
}
```
See [docs/output_format.json](docs/output_format.json) for complete field descriptions.

### Processing Pipeline
```
Raw PGN → analyze_pgn.py (UCI protocol) → lc0 analysis → JSON output → 
Training dataset → ML model → Historical game analysis
```

## Dataset

### Training Data
- **Source**: Lichess/FIDE standard rated games
- **Size**: ~100,000 games (~3.5M positions)
- **Period**: Late 2024 - Early 2025
- **Format**: PGN with player names and FIDE Elo ratings

### Historical Data (Target Application)
- **Source**: Chessmetrics database
- **Size**: ~23,000 elite games
- **Period**: 1843-2005
- **Players**: Top-20 per historical era for calibration

## Project Structure

```
elo-estimator/
├── lc0/                          # Leela Chess Zero engine (git submodule)
│   ├── src/                      # C++ source code
│   └── build/                    # Compiled binaries
├── networks/                     # Leela neural network weights
│   └── 791556.pb.gz              # Example network file
├── pgn-data/
│   ├── raw/                      # Training games
│   └── samples/                  # Small PGN files for testing
├── output/                       # Analysis output JSON files
├── scripts/                      # Python processing scripts
│   ├── analyze_pgn.py            # Main PGN analysis script
│   ├── setup_venv.ps1            # Python environment setup (Windows)
│   ├── requirements.txt          # Python dependencies
│   └── README.md                 # Scripts documentation
├── config/                       # Configuration files
│   └── lc0_config.json           # lc0 engine configuration
└── docs/                         # Documentation
    ├── PROJECT_BRIEF.md          # Project overview (brief)
    ├── config_example.md         # Config file structure documentation
    ├── output_format.json        # Output format specification
    └── sample_input.pgn          # Sample PGN data
```

## Release Status

**Release Stage**: v1.1 – feature complete for Elo estimation workflows

✅ **Completed**:
- Project structure established
- lc0 submodule configured (tracking official v0.32.0 release)
- lc0 builds successfully on Windows (MSVC + CUDA)
- Python analysis script (`analyze_pgn.py`) working with UCI protocol
- Sample PGN analysis tested (first 10 games)
- Output format validated with actual lc0 evaluations
- Process larger game batches (1000 games)
- Improved error handling and robustness
- Configuration, docs, and examples synchronized for production use

🚧 **In Progress**:
- Testing evaluation consistency across different positions
- Performance optimization for batch processing
- Automated regression benchmarking across hardware targets

🔮 **Planned**:
- Run large 100k games set of data
- Train Elo estimation model (ML component)
- Validate model accuracy on held-out test set
- Apply to historical games for calibration

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

```bash
python scripts/analyze_pgn.py <pgn_file> <output_file> [options]
```

#### Quick Test Examples

*Windows (PowerShell):*
```powershell
# Make sure Python venv is activated
.\.venv\Scripts\Activate.ps1

# Run analysis on sample PGN file (uses config defaults: 1000 nodes)
python scripts\analyze_pgn.py `
  pgn-data\samples\first10.pgn `
  output\test_analysis.json

# Run with different node count (100 nodes for quick test)
python scripts\analyze_pgn.py `
  pgn-data\samples\single.pgn `
  output\single_test_100nodes.json `
  --search.nodes=100

# Override multiple settings
python scripts\analyze_pgn.py `
  pgn-data\samples\single.pgn `
  output\quick_test.json `
  --search.nodes=50 `
  --lc0.threads=2 `
  --set max_candidates=5
```

*Linux/Mac:*
```bash
# Make sure Python venv is activated
source .venv/bin/activate

# Run analysis on sample PGN file (uses config defaults: 1000 nodes)
python scripts/analyze_pgn.py \
  pgn-data/samples/first10.pgn \
  output/test_analysis.json

# Run with different node count (100 nodes for quick test)
python scripts/analyze_pgn.py \
  pgn-data/samples/single.pgn \
  output/single_test_100nodes.json \
  --search.nodes=100

# Override multiple settings
python scripts/analyze_pgn.py \
  pgn-data/samples/single.pgn \
  output/quick_test.json \
  --search.nodes=50 \
  --lc0.threads=2 \
  --set max_candidates=5
```

Expected output: `output/test_analysis.json` with position evaluations.

For complete command-line documentation:
```powershell
python scripts\analyze_pgn.py --help
```

## Configuration

The default configuration is in `config/lc0_config.json`. Key settings:
- **Search budget**: `search.value` (default: 100 nodes) - more nodes = better quality, slower
- **Candidate moves**: `max_candidates` (default: 10) - how many top moves to include
- **lc0 options**: `backend`, `threads`, etc. - passed directly to the engine

Command-line overrides (recommended for testing):
```powershell
# Override search nodes
--search.nodes=50

# Override lc0 options
--lc0.backend=cuda-fp16 --lc0.threads=4

# Override any config value
--set max_candidates=5
```

For detailed configuration documentation, see [docs/config_example.md](docs/config_example.md).

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
**Development**: This project was almost entirely written by Claude Sonnet 4.5, with Alexis Olson serving as the driver and director

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

The lc0 engine (included as a submodule) is also licensed under GPL v3.0 by the Leela Chess Zero contributors.

---

## Known Limitations & Future Work

- **Engine**: Currently Leela-only; Stockfish support could be added for comparison
- **Formats**: PGN input only; no direct support for EPD or FEN lists

**Note**: v1.1 is stable for analysis workflows, but this remains research software. Expect occasional parameter refinements as new data and engine builds are incorporated.