# Multi-stage Dockerfile for running analyze_pgn.py on vast.ai
# Stage 1: Build lc0 with CUDA support
# Stage 2: Copy binary to smaller runtime image

# ============ Stage 1: Builder ============
FROM nvidia/cuda:12.4.0-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cmake \
    ninja-build \
    python3 \
    python3-pip \
    clang \
    libprotobuf-dev \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

# Install meson for building
RUN python3 -m pip install --no-cache-dir meson

# Build lc0 v0.32.0 with CUDA support for all GPU architectures
# Use x86-64 instead of -march=native for compatibility across different CPUs
# Use -Dnative_cuda=false to build for all major CUDA architectures (not just build machine's GPU)
# This ensures compatibility with GPUs from Pascal (1xxx) through Blackwell (5xxx) series
RUN git clone https://github.com/LeelaChessZero/lc0.git /tmp/lc0 && \
    cd /tmp/lc0 && \
    git checkout v0.32.0 && \
    CC=clang CXX=clang++ CXXFLAGS="-march=x86-64" CFLAGS="-march=x86-64" \
    ./build.sh -Dnative_cuda=false && \
    cp build/release/lc0 /lc0

# ============ Stage 2: Runtime ============
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for analysis
RUN python3 -m pip install --no-cache-dir python-chess

# Copy lc0 binary from builder stage
COPY --from=builder /lc0 /usr/local/bin/lc0

# Create working directory
WORKDIR /workspace

# Copy scripts and configuration
COPY scripts/analyze_pgn.py /workspace/
COPY scripts/run_multi_gpu.sh /workspace/
COPY scripts/check_errors.py /workspace/
COPY config/lc0_config.vastai.json /workspace/config/lc0_config.json
COPY VASTAI_USAGE.md /workspace/
COPY docs/MULTI_GPU_USAGE.md /workspace/

# Bake in BT4 neural network and PGN data for easier local testing and vast.ai deployment
RUN mkdir -p /workspace/networks
COPY networks/BT4-1024x15x32h-swa-6147500.pb.gz /workspace/networks/

# Copy specific PGN files (create directories first)
RUN mkdir -p /workspace/pgn-data/samples /workspace/pgn-data/raw
COPY pgn-data/samples/first10.pgn /workspace/pgn-data/samples/
COPY pgn-data/raw/elite_full_40k_games.pgn /workspace/pgn-data/raw/
COPY pgn-data/raw/training_full_150k_games.pgn /workspace/pgn-data/raw/

# Create output directory (can be mounted at runtime for persistent results)
RUN mkdir -p /workspace/output

# Create convenience symlinks for shorter commands
RUN ln -s /workspace/pgn-data/samples/first10.pgn /workspace/test.pgn && \
    ln -s /workspace/pgn-data/raw/elite_full_40k_games.pgn /workspace/elite.pgn && \
    ln -s /workspace/pgn-data/raw/training_full_150k_games.pgn /workspace/training.pgn && \
    ln -s /workspace/networks/BT4-1024x15x32h-swa-6147500.pb.gz /workspace/bt4.pb.gz

ENV PYTHONUNBUFFERED=1

# Default command runs bash so user can run analyze_pgn.py with custom args
CMD ["/bin/bash"]
