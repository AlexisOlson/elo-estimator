# Plan: Multi-GPU Parallelism for vast.ai Deployment

## Overview
Prepare the elo-estimator project to process ~200k games on a vast.ai instance with multiple GPUs (targeting 8, flexible for more/fewer).

**Key Discovery**: The `archive-experiments` branch already contains most of the required infrastructure! This plan focuses on cherry-picking that work and making targeted updates.

---

## What Already Exists on `archive-experiments`

| Feature | File | Status |
|---------|------|--------|
| Multi-GPU distributed mode | `scripts/analyze_pgn.py` | ✅ Complete |
| Lock file game claiming | `scripts/analyze_pgn.py` | ✅ Complete |
| Per-game JSON output | `scripts/analyze_pgn.py` | ✅ Complete |
| `--merge` to combine results | `scripts/analyze_pgn.py` | ✅ Complete |
| Dockerfile (CUDA 12.4) | `Dockerfile` | ✅ Complete |
| Docker ignore | `.dockerignore` | ✅ Complete |
| vast.ai config | `config/lc0_config.vastai.json` | ✅ Complete |
| Multi-GPU shell script | `scripts/run_multi_gpu.sh` | ✅ Complete |
| vast.ai usage guide | `VASTAI_USAGE.md` | ✅ Complete |
| Multi-GPU docs | `docs/MULTI_GPU_USAGE.md` | ✅ Complete |

### Existing Multi-GPU Architecture
```
analyze_pgn.py --work-dir=output/work --worker-id=GPU0 --lc0.backend-opts=gpu=0
analyze_pgn.py --work-dir=output/work --worker-id=GPU1 --lc0.backend-opts=gpu=1
...
analyze_pgn.py --work-dir=output/work --merge  # Combine results
```

Work directory structure (this IS the final output - no merge needed):
```
output/elite_work/
├── game_0001.json       # Completed game 1
├── game_0002.json       # Completed game 2
├── game_0003.lock       # In progress (contains worker_id, timestamp)
└── ...

output/training_work/
├── game_0001.json
├── game_0002.json
└── ...
```

**Output Strategy**: Keep individual per-game JSON files as final output. Optional merge script available if single-file format needed later.

---

## Phase 1: Cherry-Pick from Archive Branch

### 1.1 Merge or Cherry-Pick Multi-GPU Changes
**Source**: `archive-experiments` branch

Files to bring to main:
- `scripts/analyze_pgn.py` (multi-GPU additions: ~150 lines)
- `Dockerfile`
- `.dockerignore`
- `config/lc0_config.vastai.json`
- `scripts/run_multi_gpu.sh`
- `scripts/run_multi_gpu.ps1`
- `VASTAI_USAGE.md`
- `docs/MULTI_GPU_USAGE.md`

**Option A**: Full merge
```bash
git merge archive-experiments
```

**Option B**: Selective cherry-pick (if archive has unwanted changes)
```bash
git checkout archive-experiments -- Dockerfile .dockerignore
git checkout archive-experiments -- config/lc0_config.vastai.json
git checkout archive-experiments -- scripts/run_multi_gpu.sh scripts/run_multi_gpu.ps1
git checkout archive-experiments -- VASTAI_USAGE.md docs/MULTI_GPU_USAGE.md
# Then manually merge analyze_pgn.py changes
```

---

## Phase 2: Update Dockerfile for Production

### 2.1 Modifications Needed
The existing Dockerfile needs updates for the full 200k run:

```dockerfile
# Current: Copies specific test files
COPY training_uniform_1k_games.pgn /workspace/

# Update to: Mount volumes instead (don't embed PGN in image)
# Remove hardcoded PGN files from Dockerfile
# Use volume mounts at runtime
```

### 2.2 Updated Dockerfile
**File**: `Dockerfile` (MODIFY)

```dockerfile
# Stage 1: Build lc0 (keep as-is from archive)
FROM nvidia/cuda:12.4.0-devel-ubuntu22.04 AS builder
# ... existing build steps ...

# Stage 2: Runtime (update for production)
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir python-chess

COPY --from=builder /lc0 /usr/local/bin/lc0

WORKDIR /workspace
COPY scripts/analyze_pgn.py /workspace/
COPY scripts/run_multi_gpu.sh /workspace/
COPY config/lc0_config.vastai.json /workspace/config/lc0_config.json
COPY VASTAI_USAGE.md /workspace/
COPY docs/MULTI_GPU_USAGE.md /workspace/

# Data directories mounted at runtime
# /data/pgn - PGN files
# /data/networks - Neural network weights
# /data/output - Output directory

ENV PYTHONUNBUFFERED=1

CMD ["/bin/bash"]
```

---

## Phase 3: Update Configuration

### 3.1 Update vast.ai Config for 2000 Nodes
**File**: `config/lc0_config.vastai.json` (MODIFY)

```json
{
  "lc0_path": "/usr/local/bin/lc0",
  "weights": "/data/networks/BT4-1024x15x32h-swa-6147500.pb.gz",
  "search": {
    "type": "nodes",
    "value": 2000
  },
  "max_candidates": 20,
  "extra_args": [
    "--backend=cuda-fp16",
    "--threads=1",
    "--minibatch-size=64",
    "--wdl-draw-rate-reference=0.64",
    "--wdl-calibration-elo=2650",
    "--smart-pruning-factor=0.0",
    "--root-has-own-cpuct-params=true",
    "--cpuct-at-root=100.0"
  ]
}
```

Changes from archive version:
- `search.value`: 2000 (was 2000, confirm)
- `weights`: Updated path for volume mount
- `minibatch-size`: 64 (tune for larger GPUs like A100/H100)

---

## Phase 4: Create Production Run Scripts

### 4.1 Modify run_multi_gpu.sh to Support --no-merge
**File**: `scripts/run_multi_gpu.sh` (MODIFY)

Add `--no-merge` flag to skip the merge step at the end. When used, output remains as individual game files in the work directory.

### 4.2 Full Dataset Run Script
**File**: `scripts/run_full_dataset.sh` (NEW)

```bash
#!/bin/bash
# Run complete 200k game analysis on vast.ai
# Output: Individual per-game JSON files (no merge)

set -e

WORK_BASE="/data/output"
NUM_GPUS="${1:-8}"

echo "=== Elite Dataset (40k games) ==="
./run_multi_gpu.sh /data/pgn/elite_full_40k_games.pgn \
    ${WORK_BASE}/elite.json \
    $NUM_GPUS \
    --no-merge \
    --search.nodes=2000
# Output: /data/output/elite_work/game_*.json

echo "=== Training Dataset (150k games) ==="
./run_multi_gpu.sh /data/pgn/training_full_150k_games.pgn \
    ${WORK_BASE}/training.json \
    $NUM_GPUS \
    --no-merge \
    --search.nodes=2000
# Output: /data/output/training_work/game_*.json

echo "=== Complete ==="
echo "Elite results: ${WORK_BASE}/elite_work/ (40k files)"
echo "Training results: ${WORK_BASE}/training_work/ (150k files)"
```

### 4.3 Progress Monitoring Script
**File**: `scripts/check_progress.sh` (NEW)

```bash
#!/bin/bash
# Quick progress check for running analysis

WORK_DIR="${1:-.}"

completed=$(ls ${WORK_DIR}/*.json 2>/dev/null | wc -l)
in_progress=$(ls ${WORK_DIR}/*.lock 2>/dev/null | wc -l)

echo "Completed: $completed"
echo "In progress: $in_progress"
echo "---"
echo "Active workers:"
cat ${WORK_DIR}/*.lock 2>/dev/null | jq -r '.worker_id' | sort | uniq -c
```

---

## Phase 5: Testing Before Full Run

### 5.1 Local Multi-GPU Test (Windows - GTX 1070 + RTX 2080)
Single command launches both workers:
```powershell
# Using run_multi_gpu.ps1 (from archive, spawns workers in background)
.\scripts\run_multi_gpu.ps1 pgn-data/raw/training_2425_first1000.pgn output/test.json 2 --search.nodes=100

# Output: individual game files in output/test_work/
```

The script:
1. Spawns N worker processes (one per GPU)
2. Each worker claims games atomically via lock files
3. Waits for all workers to complete
4. Optionally merges (we'll add a `--no-merge` flag)

### 5.2 Docker/Linux Test
```bash
# Single command for multi-GPU
./scripts/run_multi_gpu.sh pgn-data/raw/training_2425_first1000.pgn output/test.json 2 --search.nodes=100
```

### 5.3 vast.ai Test Run
1. Rent 2-GPU instance (cheap test)
2. Upload Docker image to Docker Hub
3. Single command: `./run_multi_gpu.sh /data/pgn/training_2425_first1000.pgn /data/output/test.json 2`
4. Verify per-game JSON output in work directory

---

## Phase 6: Deployment Checklist

### 6.1 Pre-Deployment
- [ ] Merge/cherry-pick archive-experiments changes
- [ ] Update Dockerfile for volume mounts
- [ ] Update lc0_config.vastai.json for 2000 nodes
- [ ] Build and push Docker image
- [ ] Upload PGN files to cloud storage (for transfer to vast.ai)
- [ ] Upload neural network weights

### 6.2 vast.ai Setup
- [ ] Select 8-GPU instance (RTX 4090 or A100 recommended)
- [ ] Attach sufficient storage (~500GB for output)
- [ ] Pull Docker image
- [ ] Transfer PGN files and network weights
- [ ] Run test with 100 games first

### 6.3 Full Run
```bash
# On vast.ai instance
./run_multi_gpu.sh /data/pgn/elite_full_40k_games.pgn \
    /data/output/elite.json 8 --search.nodes=2000

./run_multi_gpu.sh /data/pgn/training_full_150k_games.pgn \
    /data/output/training.json 8 --search.nodes=2000
```

---

## Files Summary

### From Archive (cherry-pick)
| File | Purpose |
|------|---------|
| `scripts/analyze_pgn.py` | Multi-GPU additions (~150 lines) |
| `Dockerfile` | CUDA 12.4 multi-stage build |
| `.dockerignore` | Docker build exclusions |
| `config/lc0_config.vastai.json` | Container config |
| `scripts/run_multi_gpu.sh` | Multi-GPU orchestration |
| `scripts/run_multi_gpu.ps1` | Windows version |
| `VASTAI_USAGE.md` | Deployment guide |
| `docs/MULTI_GPU_USAGE.md` | Multi-GPU usage guide |

### New/Modified for Production
| File | Purpose |
|------|---------|
| `Dockerfile` | Update for volume mounts |
| `config/lc0_config.vastai.json` | 2000 nodes, larger minibatch |
| `scripts/run_full_dataset.sh` | Run both PGN files |
| `scripts/check_progress.sh` | Monitor progress |

---

## Execution Order

1. **Phase 1**: Cherry-pick from archive-experiments
2. **Phase 2**: Update Dockerfile for production use
3. **Phase 3**: Update config for 2000 nodes
4. **Phase 5**: Local and Docker testing
5. **Phase 4**: Create run scripts
6. **Phase 6**: Deploy to vast.ai

---

## Estimated Time Budget for 200k Games

| GPUs | Nodes | Time/Game | Total Time |
|------|-------|-----------|------------|
| 8 | 2000 | ~80 sec | ~18 days |
| 8 | 1000 | ~40 sec | ~9 days |
| 4 | 2000 | ~80 sec | ~36 days |

Recommendation: Start with 8 GPUs at 2000 nodes. Monitor first 1000 games to verify throughput.
