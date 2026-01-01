# Running analyze_pgn.py on vast.ai

This guide shows how to build and run the chess analysis on vast.ai GPU instances.

## Docker Image Specifications

- **Base Image:** NVIDIA CUDA 12.4.0-devel on Ubuntu 22.04
- **lc0 Version:** v0.32.0 (pinned release)
- **Python:** 3.10+ (from Ubuntu 22.04)
- **Dependencies:** python-chess

## Prerequisites

1. **Local files prepared:**
   - Neural network weights in `networks/` directory (e.g., `BT4-1024x15x32h-swa-6147500.pb.gz`)
   - Config file at `config/lc0_config.vastai.json` (adjust for your GPU)
   - Your PGN file to analyze

2. **vast.ai account:**
   - Sign up at https://vast.ai
   - Add funds to your account

## Step 1: Build the Docker Image

```bash
# From the elo-estimator directory
docker build -t lc0-analyzer:latest .
```

Build time: ~5-10 minutes (compiles lc0 with CUDA support)

## Step 2: Test Locally (Optional)

If you have an NVIDIA GPU locally:

```bash
docker run --gpus all -it lc0-analyzer:latest

# Inside the container, everything is in /workspace:
ls
# analyze_pgn.py  BT4-1024x15x32h-swa-6147500.pb.gz  lc0_config.json  test_fools_mate.pgn  training_uniform_1k_games.pgn  VASTAI_USAGE.md

# Quick test with fool's mate (1 game, 3 moves - very fast):
python3 analyze_pgn.py test_fools_mate.pgn test_output.json

# Full analysis on 1000 games:
python3 analyze_pgn.py training_uniform_1k_games.pgn output.json
```

## Step 3: Push to Docker Hub

```bash
# Tag for your Docker Hub account
docker tag lc0-analyzer:latest YOUR_DOCKERHUB_USERNAME/lc0-analyzer:latest

# Login and push
docker login
docker push YOUR_DOCKERHUB_USERNAME/lc0-analyzer:latest
```

## Step 4: Configure GPU Settings for vast.ai

Edit `config/lc0_config.json` to match your vast.ai GPU.


Rebuild the Docker image after changing the config.

## Step 5: Run on vast.ai

### Option A: Using vast.ai Web Interface

1. Go to https://vast.ai/console/create/
2. Select a GPU instance (recommended: RTX 3080 or better)
3. In "Image Path/Tag" enter: `YOUR_DOCKERHUB_USERNAME/lc0-analyzer:latest`
4. Launch the instance
5. SSH into the instance
6. The container has everything in `/workspace/`:
   ```bash
   cd /workspace
   ls
   # analyze_pgn.py  BT4-1024x15x32h-swa-6147500.pb.gz  lc0_config.json  test_fools_mate.pgn  training_uniform_1k_games.pgn  VASTAI_USAGE.md
   ```
7. Quick test (recommended first):
   ```bash
   python3 analyze_pgn.py test_fools_mate.pgn test_output.json
   ```
8. Run full analysis on 1000 games:
   ```bash
   python3 analyze_pgn.py training_uniform_1k_games.pgn output.json
   ```
9. Or upload your own PGN and analyze it:
   ```bash
   # From your local machine:
   scp -P PORT your_games.pgn root@IP_ADDRESS:/workspace/

   # Inside the container:
   python3 analyze_pgn.py your_games.pgn output.json
   ```

### Option B: Using vast.ai CLI

```bash
# Install vast.ai CLI
pip install vastai

# Search for instances (example: RTX 3080, <$0.30/hr)
vastai search offers 'gpu_name=RTX_3080 num_gpus=1 rentable=True verified=True' --order 'dph+'

# Rent an instance (replace INSTANCE_ID with one from search)
vastai create instance INSTANCE_ID \
  --image YOUR_DOCKERHUB_USERNAME/lc0-analyzer:latest \
  --disk 50

# SSH into instance (get SSH command from vast.ai console)
ssh -p PORT root@IP_ADDRESS

# Inside the instance, run analysis
cd /workspace
python3 analyze_pgn.py training_uniform_1k_games.pgn output.json
```

## Step 6: Transfer Files

### Upload your own PGN to instance:
```bash
# From your local machine
scp -P PORT your_games.pgn root@IP_ADDRESS:/workspace/
```

### Download results:
```bash
# From your local machine
scp -P PORT root@IP_ADDRESS:/workspace/output.json ./output/
```

## Performance Estimates

For 1000 games (~35,000 positions) at 1000 nodes per position:

| GPU | Est. Time | Cost (@ $0.20/hr) |
|-----|-----------|-------------------|
| RTX 3060 Ti | ~12 hours | ~$2.40 |
| RTX 3080 | ~6 hours | ~$1.20 |
| RTX 3090 | ~4 hours | ~$0.80 |
| RTX 4090 | ~3 hours | ~$0.60 |
| A100 | ~2 hours | ~$0.40 |

*Times are approximate and depend on position complexity*

## Monitoring Progress

The script outputs progress as it runs:

```
Analyzing game 1 (42 plies)...
  Game 1 ply 1/42: e4
  Game 1 ply 2/42: e5
  ...
  Analyzed 42 positions
  Progress saved (1/1000 games completed)
```

Output is saved incrementally, so you can download partial results if needed.

## Tips for vast.ai

1. **Choose verified hosts** - More reliable uptime
2. **Use interruptible instances** - Much cheaper if you can tolerate occasional restarts
3. **Monitor GPU utilization** - SSH in and run `nvidia-smi` to verify GPU is being used
4. **Test with small PGN first** - Run 10-20 games to verify everything works before full batch
5. **Adjust minibatch-size** - If you see OOM errors, reduce it; if GPU utilization is low, increase it

## Troubleshooting

**CUDA out of memory:**
- Reduce `--minibatch-size` in config
- Reduce `--threads`

**Slow performance:**
- Increase `--minibatch-size` (if memory allows)
- Verify GPU is being used: `nvidia-smi`
- Check if backend is correct: `cuda-fp16` for modern GPUs

**No GPU detected:**
- Ensure vast.ai instance has `--gpus all` flag
- Verify CUDA is installed in container: `nvidia-smi`

## Cost Optimization

To reduce nodes for faster/cheaper analysis:

```bash
python3 analyze_pgn.py \
  training_uniform_1k_games.pgn \
  output.json \
  --search.nodes=100  # Instead of default 1000
```

This gives 10x speedup with reduced quality (still good for many ML applications).

## File Structure in Container

All files are in `/workspace/`:
- `analyze_pgn.py` - Analysis script
- `config/lc0_config.json` - Configuration (from lc0_config.vastai.json)
- `BT4-1024x15x32h-swa-6147500.pb.gz` - Neural network weights
- `test_fools_mate.pgn` - Quick test PGN (1 game, 3 moves - fool's mate)
- `training_uniform_1k_games.pgn` - Full dataset (1000 games)
- `VASTAI_USAGE.md` - This documentation file
- `/usr/local/bin/lc0` - lc0 v0.32.0 binary