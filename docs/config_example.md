# lc0_config.json Structure

## Example Configuration

```json
{
  "lc0_path": "../lc0/build/lc0.exe",
  "weights": "../networks/BT4-1024x15x32h-swa-6147500.pb.gz",
  "search": {
    "type": "nodes",
    "value": 1000
  },
  "max_candidates": 5,
  "extra_args": [
    "--backend=cuda-fp16",
    "--threads=1",
    "--minibatch-size=22",
    "--wdl-draw-rate-reference=0.67",
    "--smart-pruning-factor=0.0"
  ]
}
```

## Configuration Fields

### Required Fields

- **`lc0_path`** (string): Path to the lc0 executable
  - Use relative or absolute path
  - Example: `"../lc0/build/lc0.exe"` (Windows) or `"../lc0/build/lc0"` (Linux/Mac)

- **`weights`** (string): Path to the neural network weights file
  - Format: `.pb.gz` (Leela protobuf format)
  - Example: `"../networks/BT4-1024x15x32h-swa-6147500.pb.gz"`

### Optional Fields

- **`search`** (object): Configure search parameters
  - `type`: `"nodes"`, `"movetime"`, `"depth"`, or `"infinite"`
  - `value`: Number corresponding to the type (e.g., 1000 nodes, 5000 milliseconds)
  - Default: `{"type": "nodes", "value": 100}`

- **`max_candidates`** (integer): Maximum number of candidate moves to analyze per position
  - Range: 1-500
  - Default: 10
  - Example: `5` (top 5 moves)

- **`extra_args`** (array of strings): Additional lc0 command-line arguments
  - All lc0 engine parameters go here
  - Format: Each argument as a separate string with `--option=value` format
  - See `lc0 --help` for all available options

### Common lc0 Parameters

#### Backend and Performance
- **`--backend=BACKEND`**: Neural network backend to use
  - Values: `cuda-fp16` (recommended for NVIDIA GPUs), `cuda`, `cuda-fp32`, `cpu`, `opencl`, etc.
  - Example: `"--backend=cuda-fp16"`

- **`--threads=N`**: Number of CPU worker threads to use
  - Range: 0-128 (0 = backend default)
  - Recommendation: Use 1-2 threads for single GPU setups
  - Example: `"--threads=1"`

- **`--minibatch-size=N`**: Batch size for GPU inference
  - Range: 0-1024 (0 = backend suggested value)
  - Must be tuned for your specific GPU and network
  - Higher values may reduce strength but increase throughput
  - Use `lc0 backendbench --clippy` to find optimal value
  - Example: `"--minibatch-size=22"` (optimal for RTX 2080 + BT4)

#### WDL (Win/Draw/Loss) Calibration
- **`--wdl-draw-rate-reference=X`**: Expected draw rate of the neural network
  - Range: 0.0-1.0
  - Network-specific value for accurate WDL rescaling
  - BT4 networks: `0.67`
  - Default networks: `0.50`
  - Example: `"--wdl-draw-rate-reference=0.67"`

- **`--wdl-calibration-elo=X`**: Elo rating of the active side for WDL sharpening
  - Range: 0.0-10000.0
  - Higher Elo = sharper (more decisive) WDL values
  - Use `0` to retain raw WDL without sharpening/softening
  - Use `3300` for very strong engine-level play
  - Adjusts for time control relative to rapid
  - Example: `"--wdl-calibration-elo=3300"`

#### Search Configuration
- **`--smart-pruning-factor=X`**: Aggressiveness of search pruning
  - Range: 0.0-10.0
  - `0.0` = disabled (no pruning)
  - `1.33` = default
  - Higher values prune more aggressively (faster but potentially less accurate)
  - Example: `"--smart-pruning-factor=0.0"` (disable for maximum accuracy)

## Network-Specific Settings

### BT4 Networks
BT4 networks have specific optimal settings:

```json
"extra_args": [
  "--backend=cuda-fp16",
  "--threads=1",
  "--minibatch-size=22",
  "--wdl-draw-rate-reference=0.67",
  "--wdl-calibration-elo=3300",
  "--smart-pruning-factor=0.0"
]
```

**Key BT4 settings:**
- **Draw rate reference**: `0.67` - BT4 networks predict higher draw rates than standard nets
- **WDL calibration Elo**: `3300` - Calibrates WDL for strong engine-level play
- **Smart pruning**: `0.0` - Disabled for maximum accuracy in analysis
- **Minibatch size**: `22` - Optimal for RTX 2080 (use `backendbench --clippy` for your GPU)

### Minibatch Size Tuning

The optimal `--minibatch-size` depends on your GPU and network size. Use lc0's backend benchmark:

```bash
lc0 backendbench --backend=cuda-fp16 --weights=your_network.pb.gz --clippy
```

Clippy will recommend optimal minibatch sizes for different time controls.

## Command-Line Overrides

All config values can be overridden from the command line:

```bash
# Override search nodes
python scripts/analyze_pgn.py game.pgn output.json --search.nodes=50

# Override lc0 options
python scripts/analyze_pgn.py game.pgn output.json --lc0.threads=2 --lc0.backend=cpu

# Override any config field
python scripts/analyze_pgn.py game.pgn output.json --set max_candidates=3
```

Command-line arguments take precedence over config file values.
