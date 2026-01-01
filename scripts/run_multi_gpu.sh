#!/bin/bash
# Helper script to launch multiple GPU workers for distributed PGN analysis
#
# Usage: ./scripts/run_multi_gpu.sh <pgn_file> <output_file> <num_gpus> [additional_args...]
#
# Example:
#   ./scripts/run_multi_gpu.sh games.pgn output.json 4 --search.nodes=1000

set -e

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <pgn_file> <output_file> <num_gpus> [additional_args...]"
    echo ""
    echo "Example:"
    echo "  $0 games.pgn output.json 4 --search.nodes=1000"
    exit 1
fi

PGN_FILE="$1"
OUTPUT_FILE="$2"
NUM_GPUS="$3"
shift 3
EXTRA_ARGS="$@"

# Derive work directory from output file
WORK_DIR="${OUTPUT_FILE%.json}_work"

echo "Starting distributed PGN analysis:"
echo "  PGN file: $PGN_FILE"
echo "  Output file: $OUTPUT_FILE"
echo "  Work directory: $WORK_DIR"
echo "  Number of GPUs: $NUM_GPUS"
echo "  Extra args: $EXTRA_ARGS"
echo ""

# Create work directory
mkdir -p "$WORK_DIR"

# Launch workers in background
PIDS=()
for ((gpu=0; gpu<NUM_GPUS; gpu++)); do
    WORKER_ID="GPU${gpu}"
    LOG_FILE="${WORK_DIR}/${WORKER_ID}.log"

    echo "Launching worker $WORKER_ID (logging to $LOG_FILE)..."

    python scripts/analyze_pgn.py "$PGN_FILE" "$OUTPUT_FILE" \
        --work-dir="$WORK_DIR" \
        --worker-id="$WORKER_ID" \
        --lc0.backend-opts="gpu=$gpu" \
        $EXTRA_ARGS \
        > "$LOG_FILE" 2>&1 &

    PIDS+=($!)
    echo "  Started with PID ${PIDS[$gpu]}"
done

echo ""
echo "All workers launched. Waiting for completion..."
echo "Monitor progress with: tail -f ${WORK_DIR}/GPU*.log"
echo ""

# Wait for all workers to complete
for ((gpu=0; gpu<NUM_GPUS; gpu++)); do
    PID=${PIDS[$gpu]}
    echo "Waiting for GPU${gpu} (PID $PID)..."
    wait $PID
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "WARNING: GPU${gpu} exited with code $EXIT_CODE"
    else
        echo "GPU${gpu} completed successfully"
    fi
done

echo ""
echo "All workers finished. Merging results..."

# Merge results
python scripts/analyze_pgn.py "$PGN_FILE" "$OUTPUT_FILE" \
    --work-dir="$WORK_DIR" \
    --merge

echo ""
echo "Done! Final output: $OUTPUT_FILE"
echo ""

# Show summary
COMPLETED=$(ls "$WORK_DIR"/game_*.json 2>/dev/null | wc -l)
LOCKS=$(ls "$WORK_DIR"/game_*.lock 2>/dev/null | wc -l)

echo "Summary:"
echo "  Completed games: $COMPLETED"
echo "  Remaining locks: $LOCKS"

if [ $LOCKS -gt 0 ]; then
    echo ""
    echo "WARNING: Some lock files remain. This may indicate crashed workers."
    echo "Review logs in $WORK_DIR/*.log"
fi
