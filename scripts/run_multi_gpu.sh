#!/bin/bash
# Helper script to launch multiple GPU workers for distributed PGN analysis
#
# Usage: ./scripts/run_multi_gpu.sh <pgn_file> [num_gpus] --output-dir=DIR [options...]
#
# Example:
#   # Auto-detect GPUs
#   ./scripts/run_multi_gpu.sh games.pgn --output-dir=output/run1 --search.nodes=1000
#
#   # Specify GPU count explicitly
#   ./scripts/run_multi_gpu.sh games.pgn 4 --output-dir=output/run1 --search.nodes=1000
#
#   # With merge - combine into single file
#   ./scripts/run_multi_gpu.sh games.pgn --output-dir=output/run1 --merge=results.json --search.nodes=2000

set -e

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <pgn_file> [num_gpus] --output-dir=DIR [options...]"
    echo ""
    echo "Arguments:"
    echo "  num_gpus             Number of GPUs to use (default: auto-detect)"
    echo ""
    echo "Required:"
    echo "  --output-dir=DIR     Directory for individual game files and logs"
    echo ""
    echo "Options:"
    echo "  --merge=FILE         Merge individual games into single output file"
    echo "  --search.nodes=N     Number of nodes to search per position"
    echo "  --lc0.OPTION=VALUE   Pass options to lc0"
    echo ""
    echo "Examples:"
    echo "  # Auto-detect GPUs"
    echo "  $0 games.pgn --output-dir=output/run1 --search.nodes=1000"
    echo ""
    echo "  # Specify GPU count"
    echo "  $0 games.pgn 4 --output-dir=output/run1 --search.nodes=1000"
    echo ""
    echo "  # With merge - combine results into single file"
    echo "  $0 games.pgn --output-dir=output/run1 --merge=results.json --search.nodes=2000"
    exit 1
fi

PGN_FILE="$1"
shift 1

# Check if second argument is a number (num_gpus) or an option
if [[ "$1" =~ ^[0-9]+$ ]]; then
    NUM_GPUS="$1"
    shift 1
else
    # Auto-detect GPUs using nvidia-smi
    NUM_GPUS=$(nvidia-smi --list-gpus 2>/dev/null | wc -l)
    if [ "$NUM_GPUS" -eq 0 ]; then
        echo "Error: No GPUs detected. Please specify number of GPUs manually."
        exit 1
    fi
    echo "Auto-detected $NUM_GPUS GPU(s)"
fi

# Parse arguments
OUTPUT_DIR=""
MERGE_FILE=""
FILTERED_ARGS=()

for arg in "$@"; do
    if [[ "$arg" == --output-dir=* ]]; then
        OUTPUT_DIR="${arg#*=}"
    elif [[ "$arg" == --merge=* ]]; then
        MERGE_FILE="${arg#*=}"
    elif [ "$arg" = "--merge" ]; then
        echo "Error: --merge requires a filename (e.g., --merge=results.json)"
        exit 1
    else
        FILTERED_ARGS+=("$arg")
    fi
done
EXTRA_ARGS="${FILTERED_ARGS[@]}"

# Validate required arguments
if [ -z "$OUTPUT_DIR" ]; then
    echo "Error: --output-dir is required"
    exit 1
fi

WORK_DIR="$OUTPUT_DIR"

echo "Starting distributed PGN analysis:"
echo "  PGN file: $PGN_FILE"
echo "  Output directory: $WORK_DIR"
if [ -n "$MERGE_FILE" ]; then
    echo "  Merge output: $MERGE_FILE"
fi
echo "  Number of GPUs: $NUM_GPUS"
echo "  Extra args: $EXTRA_ARGS"
echo ""

# Create work directory
mkdir -p "$WORK_DIR"

# Launch workers in background
# Note: OUTPUT_FILE is required by analyze_pgn.py but not used when --work-dir is specified
DUMMY_OUTPUT="$WORK_DIR/unused.json"

PIDS=()
for ((gpu=0; gpu<NUM_GPUS; gpu++)); do
    WORKER_ID="GPU${gpu}"
    LOG_FILE="${WORK_DIR}/${WORKER_ID}.log"

    echo "Launching worker $WORKER_ID (logging to $LOG_FILE)..."

    PYTHONUNBUFFERED=1 python3 -u analyze_pgn.py "$PGN_FILE" "$DUMMY_OUTPUT" \
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

# Progress monitoring loop
echo "Monitoring progress (Ctrl+C to stop workers)..."
while true; do
    # Check if workers are still running
    any_running=false
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            any_running=true
            break
        fi
    done

    if [ "$any_running" = false ]; then
        break
    fi

    # Calculate progress
    completed=$(ls "${WORK_DIR}"/game_*.json 2>/dev/null | wc -l)
    active=$(ls "${WORK_DIR}"/game_*.lock 2>/dev/null | wc -l)

    # Build status display showing which game each GPU is working on
    status_line="Status: $completed completed | "

    # Read lock files to see which game each worker is processing
    declare -A worker_games
    for lock_file in "${WORK_DIR}"/game_*.lock; do
        if [ -f "$lock_file" ]; then
            # Extract worker_id and game_idx from lock file JSON
            worker_info=$(python3 -c "import json; data=json.load(open('$lock_file')); print(f\"{data['worker_id']}:{data['game_idx']}\")" 2>/dev/null)
            if [ -n "$worker_info" ]; then
                worker_id="${worker_info%%:*}"
                game_idx="${worker_info##*:}"
                worker_games["$worker_id"]="$game_idx"
            fi
        fi
    done

    # Display each GPU's current game
    for ((gpu=0; gpu<NUM_GPUS; gpu++)); do
        worker_id="GPU${gpu}"
        if [ -n "${worker_games[$worker_id]}" ]; then
            status_line+="${worker_id}=game${worker_games[$worker_id]} "
        else
            status_line+="${worker_id}=idle "
        fi
    done

    # Clear line and display status
    echo -ne "\r\033[K${status_line}"

    sleep 1
done

# Final wait to collect exit codes
echo -e "\nAll workers finished. Collecting final status..."
for ((gpu=0; gpu<NUM_GPUS; gpu++)); do
    PID=${PIDS[$gpu]}
    wait $PID
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "WARNING: GPU${gpu} (PID $PID) exited with code $EXIT_CODE"
    fi
done

echo ""

# Show summary
COMPLETED=$(ls "$WORK_DIR"/game_*.json 2>/dev/null | wc -l)
LOCKS=$(ls "$WORK_DIR"/game_*.lock 2>/dev/null | wc -l)

if [ -n "$MERGE_FILE" ]; then
    echo "All workers finished. Merging results..."

    # Merge results
    python3 analyze_pgn.py "$PGN_FILE" "$MERGE_FILE" \
        --work-dir="$WORK_DIR" \
        --merge

    echo ""
    echo "Done! Final output: $MERGE_FILE"
    echo ""
    echo "Summary:"
    echo "  Completed games: $COMPLETED"
    echo "  Remaining locks: $LOCKS"
else
    echo "All workers finished. Skipping merge (use --merge=FILE to combine results)."
    echo ""
    echo "Done! Individual game files in: $WORK_DIR/"
    echo ""
    echo "Summary:"
    echo "  Completed games: $COMPLETED"
    echo "  Remaining locks: $LOCKS"
    echo ""
    echo "To merge later, run:"
    echo "  python3 analyze_pgn.py $PGN_FILE OUTPUT.json --work-dir=$WORK_DIR --merge"
fi

if [ $LOCKS -gt 0 ]; then
    echo ""
    echo "WARNING: Some lock files remain. This may indicate crashed workers."
    echo "Review logs in $WORK_DIR/*.log"
fi
