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

# Build lc0 v0.32.0 with CUDA support
# Use x86-64 instead of -march=native for compatibility across different CPUs
RUN git clone https://github.com/LeelaChessZero/lc0.git /tmp/lc0 && \
    cd /tmp/lc0 && \
    git checkout v0.32.0 && \
    CC=clang CXX=clang++ CXXFLAGS="-march=x86-64" CFLAGS="-march=x86-64" ./build.sh && \
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

# Copy all required files directly to workspace
COPY config/lc0_config.vastai.json /workspace/config/lc0_config.json
COPY networks/BT4-1024x15x32h-swa-6147500.pb.gz /workspace/
COPY scripts/analyze_pgn.py /workspace/
COPY training_uniform_1k_games.pgn /workspace/
COPY test_fools_mate.pgn /workspace/
COPY VASTAI_USAGE.md /workspace/

# Default command runs bash so user can run analyze_pgn.py with custom args
CMD ["/bin/bash"]
