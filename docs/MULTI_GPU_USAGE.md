# Multi-GPU Distributed Processing Guide

The `analyze_pgn.py` script now supports distributed processing across multiple GPUs. Each GPU worker can claim and process games independently, with atomic locking to prevent duplicate work.

## Overview

When running in distributed mode:
- Each worker atomically claims games using lock files
- Individual game results are written to separate JSON files
- Workers automatically skip games that are already complete or claimed by others
- After all workers finish, results can be merged into a single output file

## Quick Start

### 1. Launch Multiple Workers (one per GPU)

Each worker should specify:
- The same `--work-dir` (for coordination)
- A unique `--worker-id` (for tracking)
- GPU-specific lc0 options (to target the specific GPU)

**Worker 1 (GPU 0):**
```bash
python scripts/analyze_pgn.py games.pgn output.json \
  --work-dir=output/work \
  --worker-id=GPU0 \
  --lc0.backend-opts=gpu=0
```

**Worker 2 (GPU 1) - run simultaneously in another terminal:**
```bash
python scripts/analyze_pgn.py games.pgn output.json \
  --work-dir=output/work \
  --worker-id=GPU1 \
  --lc0.backend-opts=gpu=1
```

**Worker 3 (GPU 2):**
```bash
python scripts/analyze_pgn.py games.pgn output.json \
  --work-dir=output/work \
  --worker-id=GPU2 \
  --lc0.backend-opts=gpu=2
```

### 2. Merge Results

After all workers complete, merge the individual game files:

```bash
python scripts/analyze_pgn.py games.pgn output.json \
  --work-dir=output/work \
  --merge
```

This creates a single `output.json` file in the standard format.

## Work Directory Structure

The work directory contains:

```
output/work/
├── game_0001.json       # Completed game 1
├── game_0002.json       # Completed game 2
├── game_0003.lock       # Game 3 currently being processed
├── game_0004.json       # Completed game 4
└── ...
```

- `.json` files: Completed games
- `.lock` files: Games currently being processed (contain worker ID and timestamp)

## Resume Capability

If workers crash or are interrupted, you can safely restart them:
- Completed games (`.json` files exist) are automatically skipped
- Stale lock files (from crashed workers) can be manually removed to allow reprocessing

To remove stale locks:
```bash
# On Linux/macOS
find output/work -name "*.lock" -delete

# On Windows PowerShell
Remove-Item output/work/*.lock
```

## Advanced Usage

### Custom Config and Search Parameters

```bash
# Worker with custom config and search settings
python scripts/analyze_pgn.py games.pgn output.json \
  --config=config/lc0_config.json \
  --work-dir=output/work \
  --worker-id=GPU0 \
  --lc0.backend-opts=gpu=0 \
  --search.nodes=1000
```

### Using CUDA Backend

```bash
# Specify CUDA backend with specific GPU
python scripts/analyze_pgn.py games.pgn output.json \
  --work-dir=output/work \
  --worker-id=GPU0 \
  --lc0.backend=cuda-fp16 \
  --lc0.backend-opts=gpu=0
```

### Docker/Container Setup

When running in containers, mount the same work directory:

```bash
# Container 1
docker run --gpus '"device=0"' -v $(pwd)/output/work:/work ... \
  python analyze_pgn.py games.pgn output.json --work-dir=/work --worker-id=GPU0

# Container 2
docker run --gpus '"device=1"' -v $(pwd)/output/work:/work ... \
  python analyze_pgn.py games.pgn output.json --work-dir=/work --worker-id=GPU1
```

## Monitoring Progress

Each worker prints its progress:
```
[GPU0] Claimed game 5
Analyzing game 5 (142 plies)...
  Game 5 ply 142/142: Qxf7+
  Analyzed 142 positions
[GPU0] Game 5 complete (3 processed by this worker)
```

Check work directory to see overall progress:
```bash
# Count completed games
ls output/work/*.json | wc -l

# Count active locks
ls output/work/*.lock | wc -l
```

## Tips for Optimal Performance

1. **Balance the load**: If you have N GPUs and M games, all GPUs will naturally balance work by claiming games as they become available.

2. **Use fast storage**: Put the work directory on fast local storage (SSD/NVMe) to minimize lock file I/O overhead.

3. **Monitor GPU utilization**: Use `nvidia-smi` to verify all GPUs are being utilized.

4. **Batch processing**: For very large PGN files, consider splitting into smaller batches and running multiple work directories in parallel.

## Troubleshooting

### Game stuck with old lock file
If a worker crashes, it may leave a stale lock file. Check the timestamp in the lock file:
```bash
cat output/work/game_0042.lock
# {"worker_id": "GPU1", "timestamp": 1699564321.123, "game_idx": 42}
```

If it's old, manually remove it:
```bash
rm output/work/game_0042.lock
```

### Workers not finding games
Verify all workers are using:
- The same input PGN file
- The same work directory path
- Different worker IDs

### Merge fails
Ensure all `.lock` files are removed before merging. Only completed `.json` files should remain.

## Performance Comparison

**Single GPU (legacy mode):**
- 100 games × 50 plies × 1000 nodes = ~2-3 hours

**4 GPUs (distributed mode):**
- Same workload = ~30-45 minutes
- Near-linear speedup with minimal overhead