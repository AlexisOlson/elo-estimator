# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-10-23

### Added
- **analyze_pgn.py**: Added `ClearTree` UCI command before each position search to ensure fresh tree state
  - Prevents search tree pollution between positions
  - Improves evaluation consistency across positions
  - Applied to both main searches and focused single-move searches

### Changed
- **Documentation**: Comprehensive cleanup and reorganization
  - Consolidated redundant sections in README.md
  - Separated common vs advanced lc0 parameters in config_example.md
  - Streamlined output format notes (14 → 8 notes, removing redundancies)
  - Removed unnecessary `--config` flags from examples (uses default path)
  - Improved Configuration section with concrete examples

## [1.1.0] - 2025-10-19

### Changed
- **analyze_pgn.py**: Improved error handling and intermediate data saving efficiency
- **reformat_json.py**: Refactored code for better maintainability and performance
- Cleaned up JSON formatting across output files (removed trailing spaces in move strings)

### Fixed
- JSON output formatting inconsistencies in candidate move strings
- Intermediate data persistence during long-running analysis sessions

## [1.0.0] - 2025-10-19

### Initial Release

This is the first stable release of the Chess Elo Estimator project, providing a complete workflow for analyzing chess games with Leela Chess Zero and preparing data for machine learning-based Elo estimation.

### Added

#### Core Features
- **PGN Analysis Pipeline**: Full integration with Leela Chess Zero via UCI protocol
- **analyze_pgn.py**: Main script for analyzing chess positions with configurable parameters
- **JSON Output Format**: Structured output with move evaluations, candidate moves, and WDL statistics
- **Configuration System**: JSON-based configuration with command-line override support
- **Incremental Progress**: Safe restart capability for long batch processing runs

#### Move Evaluation
- Complete move ranking across all legal moves (not just MultiPV)
- Played move evaluation with rank, visits, policy, Q-value, and WDL statistics
- Top-N candidate moves with comprehensive statistics
- Proper handling of moves outside MultiPV window via focused search
- Visit-based ranking matching LC0's internal criteria (visits > Q-value > policy)

#### Data Extraction
- PGN metadata capture (players, ratings, event info, ECO codes)
- Position-level FEN export
- Total visits calculation across all legal moves
- Visits on better moves (waste metric) calculation
- Side-to-move perspective for all evaluations

#### Configuration & Flexibility
- Configurable search budget (nodes, movetime, depth, or infinite)
- Adjustable candidate move count (max_candidates)
- LC0 parameter passthrough (backend, threads, minibatch-size, WDL calibration)
- Command-line overrides for testing without modifying config
- Support for multiple override formats (--search.nodes, --lc0.threads, --set)

#### Documentation
- Comprehensive README with installation, usage, and examples
- Project structure and architecture documentation
- Output format specification (docs/output_format.json)
- Configuration guide (docs/config_example.md)
- Sample input PGN files for testing
- Command-line usage guide with correct syntax

#### Build System
- LC0 submodule integration (v0.32.0)
- Windows build support (MSVC + CUDA)
- Python virtual environment setup scripts
- Requirements management

#### Utilities
- **reformat_json.py**: JSON formatting utility for consistent output alignment
- **setup_venv.ps1**: PowerShell script for Python environment setup

### Technical Details

#### Engine Integration
- Unmodified LC0 v0.32.0 via UCI protocol
- Fixed node counts for consistent evaluation depth
- VerboseMoveStats parsing for comprehensive move data
- SAN (Standard Algebraic Notation) output without intermediate files

#### Quality Assurance
- Proper error handling for invalid moves and positions
- Validation of configuration parameters
- Safe handling of edge cases (moves outside MultiPV, book positions, etc.)
- Progress reporting during batch processing

#### Performance
- Efficient UCI communication with subprocess management
- Minimal memory overhead with streaming JSON output
- Support for parallel execution via multiple instances

### Project Structure
```
elo-estimator/
├── lc0/                    # LC0 engine submodule
├── networks/               # Neural network weights
├── pgn-data/              # Input PGN files
│   ├── raw/               # Training data (gitignored)
│   └── samples/           # Sample/test files
├── output/                # Analysis results
├── scripts/               # Python processing scripts
├── config/                # Configuration files
└── docs/                  # Documentation
```

### Dependencies
- Python 3.8+
- python-chess 1.11.2
- Leela Chess Zero (included as submodule)
- CUDA Toolkit 11.x or 12.x (for GPU support)

### Known Limitations
- Requires CUDA-capable NVIDIA GPU for reasonable performance
- Processing speed depends on hardware and node count settings

### Future Plans
- Large 100k games analysis
- ML model training for Elo prediction
- Historical game calibration
- Performance optimization for batch processing
- Automated regression testing

---

## Release Notes

This v1.0 release represents a feature-complete analysis workflow, validated with:
- Single game analysis (smoke tests)
- 10-game batch processing
- 1,000-game batch processing (training_2425_first1000.pgn)

The system is ready for large-scale data collection (100K+ games) for ML training.

### Attribution
This project was almost entirely written by Claude Sonnet 4.5, with Alexis Olson serving as the driver and director.

### License
GNU General Public License v3.0 - See LICENSE file for details.

[1.1.0]: https://github.com/AlexisOlson/elo-estimator/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/AlexisOlson/elo-estimator/releases/tag/v1.0.0
