# Running elo-estimator on vast.ai

Complete guide for running chess position analysis on vast.ai GPU instances with multi-GPU support and resumable jobs.

## What's Included in the Docker Image

**Everything is pre-installed and ready to use:**
- ✅ lc0 v0.32.0 (compiled with CUDA support for all GPU architectures)
- ✅ BT4 neural network (1024x15x32h, ~350MB)
- ✅ All PGN datasets:
  - `elite.pgn` → 40,000 elite games
  - `training.pgn` → 150,000 training games
  - `test.pgn` → 10 sample games (for quick testing)
- ✅ Multi-GPU distributed processing script
- ✅ Python dependencies (python-chess)

**No file uploads needed!** Just launch and run.

## Quick Start

### 1. Push Image to Docker Hub

```bash
# Build locally (if you haven't already)
docker build -t elo-estimator .

# Tag for Docker Hub
docker tag elo-estimator alexisolson/elo-estimator:latest

# Push
docker login
docker push alexisolson/elo-estimator:latest
```

### 2. Launch on vast.ai

**Web Interface:**
1. Go to https://vast.ai/console/create/
2. Select GPU instance (recommended: RTX 3060 Ti or better)
3. Image: `alexisolson/elo-estimator:latest`
4. Disk: 10GB minimum (for outputs)
5. Launch instance
6. Copy SSH command and connect

**CLI Method:**
```bash
# Install CLI
pip install vastai

# Search for cheap GPUs
vastai search offers 'gpu_name=RTX_3060_Ti num_gpus=1 rentable=True' --order 'dph+'

# Rent instance
vastai create instance INSTANCE_ID \
  --image alexisolson/elo-estimator:latest \
  --disk 10
```

### 3. Run Your First Test

SSH into the instance and run:

```bash
cd /workspace

# Quick test (10 games, ~30 seconds with 100 nodes, auto-detect GPUs)
./run_multi_gpu.sh test.pgn --output-dir=output/test --search.nodes=100

# Check output
ls -lh output/test/
```

## Basic Usage

### Multi-GPU Analysis

```bash
# Analyze 40k elite games (auto-detect GPUs, individual game files only)
./run_multi_gpu.sh elite.pgn --output-dir=output/elite

# Analyze 150k training games and merge into single file (auto-detect GPUs)
./run_multi_gpu.sh training.pgn --output-dir=output/training --merge=training_results.json

# Or specify GPU count explicitly
./run_multi_gpu.sh elite.pgn 4 --output-dir=output/elite
```

The script automatically:
- Splits work across GPUs
- Avoids duplicate work with atomic locking
- Optionally merges results into single output file
- Shows progress in real-time

### Custom Search Settings

```bash
# Faster analysis (100 nodes instead of default 1000)
./run_multi_gpu.sh elite.pgn --output-dir=output/elite --search.nodes=100

# Deeper analysis (10000 nodes)
./run_multi_gpu.sh elite.pgn --output-dir=output/elite --search.nodes=10000
```

## Resumable Jobs with Persistent Storage

### Why Use Persistent Storage?

Without persistent storage:
- ❌ Instance dies → all progress lost
- ❌ Can't pause and resume
- ❌ Can't scale across multiple instances

With persistent storage:
- ✅ Survives instance interruptions
- ✅ Resume from where you left off
- ✅ Run multiple instances on same dataset
- ✅ Results persist after instance destruction

### Setup Persistent Storage

**Option 1: Template Storage (Recommended)**

When creating instance via web interface:
1. Expand "Advanced Options"
2. Find "Template Storage" or "Persistent Storage"
3. Create new template (e.g., "chess-analysis-storage")
4. Mount to: `/workspace/output`

**Option 2: Instance Disk (Simple but Less Safe)**

Just specify `--disk 50` when creating instance. Data in `/workspace/output` persists as long as you don't destroy the instance.

### Running with Persistent Storage

```bash
cd /workspace

# Output automatically goes to /workspace/output (mounted storage)
./run_multi_gpu.sh elite.pgn --output-dir=output/elite

# If instance crashes or is destroyed:
# 1. Spin up new instance with same storage mounted
# 2. Run the same command
# 3. It automatically resumes from last completed game!
```

**How resumability works:**
- Each completed game → saved to `output/elite/game_0001.json`, etc.
- On restart → script checks what's already done
- Skips completed games → only processes remaining ones
- Optionally merge all individual files with `--merge=results.json`

## Multi-Instance Distributed Processing

Scale horizontally by running **multiple vast.ai instances** on the **same mounted storage**.

### Setup

**Instance 1 (4 GPUs):**
```bash
cd /workspace
./run_multi_gpu.sh elite.pgn --output-dir=output/elite
```

**Instance 2 (8 GPUs) - running simultaneously:**
```bash
cd /workspace
./run_multi_gpu.sh elite.pgn --output-dir=output/elite
```

**Instance 3 (4 GPUs) - also running simultaneously:**
```bash
cd /workspace
./run_multi_gpu.sh elite.pgn --output-dir=output/elite
```

All instances auto-detect their GPUs and coordinate via lock files. Each GPU:
1. Grabs next unclaimed game
2. Processes it
3. Saves to shared storage
4. Moves to next game

### Merging Results

After all instances complete (or you stop them):

```bash
# On any instance with access to the storage
python3 analyze_pgn.py elite.pgn output/elite/elite_results.json \
  --work-dir=output/elite \
  --merge
```

This combines all individual game files into final `elite_results.json`.

## Monitoring Progress

### Live Progress

```bash
# In another SSH session
tail -f output/elite/GPU*.log
```

### Check Completion Status

```bash
# Count completed games
ls output/elite/game_*.json | wc -l

# Count active workers
ls output/elite/game_*.lock | wc -l

# Expected total (for elite.pgn)
echo "40000"
```

## Performance Estimates

Analysis speed for 1000 nodes/position (default):

| GPU | Games/Hour (1 GPU) | Cost/1000 Games (@$0.20/hr) |
|-----|-------------------|----------------------------|
| RTX 3060 Ti | ~100 | ~$0.50 |
| RTX 3080 | ~200 | ~$0.25 |
| RTX 3090 | ~300 | ~$0.17 |
| RTX 4090 | ~400 | ~$0.13 |
| A100 | ~600 | ~$0.08 |

**Multi-GPU scales linearly:** 4x RTX 3080 → ~800 games/hour

**For 150k training games:**
- 4x RTX 4090 → ~94 hours → ~$375 @ $0.20/hr
- 8x RTX 4090 (2 instances) → ~47 hours → ~$375 @ $0.20/hr

## Cost Optimization

### Reduce Node Count

```bash
# 10x faster, lower quality (still good for many ML applications)
./run_multi_gpu.sh elite.pgn --output-dir=output/elite --search.nodes=100
```

### Use Interruptible Instances

- Much cheaper (often 50-70% discount)
- Use with persistent storage for resumability
- Perfect for large batch jobs

### Spot Pricing

Search for cheapest instances:
```bash
vastai search offers 'gpu_name=RTX_4090 num_gpus>=2' --order 'dph+'
```

## File Structure in Container

```
/workspace/
├── analyze_pgn.py              # Main analysis script
├── run_multi_gpu.sh            # Multi-GPU helper script
├── config/
│   └── lc0_config.json         # lc0 configuration
├── networks/
│   └── BT4-1024x15x32h-swa-6147500.pb.gz
├── pgn-data/
│   ├── raw/
│   │   ├── elite_full_40k_games.pgn
│   │   └── training_full_150k_games.pgn
│   └── samples/
│       └── first10.pgn
├── output/                     # Mount persistent storage here
├── test.pgn -> pgn-data/samples/first10.pgn      (symlink)
├── elite.pgn -> pgn-data/raw/elite_full_40k_games.pgn  (symlink)
├── training.pgn -> pgn-data/raw/training_full_150k_games.pgn  (symlink)
└── bt4.pb.gz -> networks/BT4-1024x15x32h-swa-6147500.pb.gz  (symlink)
```

## Advanced Usage

### Custom lc0 Options

```bash
# Use FP16 backend
./run_multi_gpu.sh elite.pgn --output-dir=output/elite --lc0.backend=cuda-fp16

# Adjust threads per worker
./run_multi_gpu.sh elite.pgn --output-dir=output/elite --lc0.threads=4
```

### Manual Analysis (Without run_multi_gpu.sh)

```bash
# Single process, no work directory
python3 analyze_pgn.py test.pgn output.json

# Distributed mode with work directory
python3 analyze_pgn.py elite.pgn final.json \
  --work-dir=work \
  --worker-id=GPU0 \
  --lc0.backend-opts=gpu=0
```

### Using Your Own PGN Files

Upload via SCP:
```bash
# From your local machine
scp -P PORT your_games.pgn root@VAST_IP:/workspace/

# On vast.ai instance
./run_multi_gpu.sh your_games.pgn --output-dir=output/your_run
```

### Download Results

```bash
# From your local machine (download merged file)
scp -P PORT root@VAST_IP:/workspace/output/elite/elite_results.json ./

# Or download all individual game files
scp -r -P PORT root@VAST_IP:/workspace/output/elite/ ./
```

## Troubleshooting

### CUDA Out of Memory

Reduce batch size in config or use fewer nodes:
```bash
./run_multi_gpu.sh elite.pgn --output-dir=output/elite --search.nodes=500
```

### Slow Performance

1. Check GPU utilization:
   ```bash
   watch -n 1 nvidia-smi
   ```

2. Verify correct backend:
   ```bash
   grep backend config/lc0_config.json
   # Should be "cuda-fp16" for modern GPUs
   ```

3. Check logs for errors:
   ```bash
   tail -f output/elite/GPU0.log
   ```

### Instance Interrupted

If using persistent storage:
1. Spin up new instance with same storage mounted
2. Run the exact same command
3. It resumes automatically - already completed games are skipped

### Lock Files Stuck

If you killed workers ungracefully:
```bash
# Check for orphaned locks
ls output/elite/*.lock

# Clean up if no workers are actually running
rm output/elite/*.lock
```

## Tips for Success

1. **Always use persistent storage** for jobs longer than 1 hour
2. **Test with test.pgn first** to verify everything works
3. **Use interruptible instances** to save 50-70% on cost
4. **Monitor with nvidia-smi** to ensure GPUs are utilized
5. **Scale horizontally** with multiple instances for huge datasets
6. **Keep output directory** until after successful merge (if merging)
7. **Skip --merge flag** when running multiple instances simultaneously (merge later)

## Support

- Docker image issues: Check your local build logs
- lc0 errors: See config/lc0_config.json for options
- vast.ai specific: https://vast.ai/docs/
- Script bugs: Check logs in work_dir/*.log
