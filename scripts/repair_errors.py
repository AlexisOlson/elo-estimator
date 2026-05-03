#!/usr/bin/env python3
"""Detect, re-run, and verify games with non-reproducible lc0 batch-parallelism artifacts.

About 0.17% of games in production runs hit one of Jeff Sonas's four error categories:
  1. played move not evaluated
  2. played move not in candidate moves
  3. candidate moves include 0 visits
  4. candidate moves include blank eval(s)

These do not reproduce on rerun. This script automates the detect -> rerun -> verify
loop end-to-end, producing a clean output directory ready for
convert_json_to_parquet.py, or a loud `repair_failures.json` report listing games that
fail repeatedly.

Usage:
  python scripts/repair_errors.py SOURCE_PGN OUTPUT_DIR [options]

The script re-runs in place: bad game_NNNNNN.json files are quarantined, then
analyze_pgn.py workers are spawned against the same OUTPUT_DIR. The pipeline's
existing skip-on-existing-JSON behavior means only the missing (bad) games are
re-processed; the rest are passed over after a header read.
"""

import argparse
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

import chess
import chess.pgn

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from check_errors import check_game


GAME_FILE_RE = re.compile(r"^game_(\d{6})\.json$")
LOCK_FILE_RE = re.compile(r"^game_(\d{6})\.lock$")


def find_game_files(output_dir: pathlib.Path) -> List[pathlib.Path]:
    """Return sorted list of game_NNNNNN.json files in output_dir (top level only)."""
    return sorted(
        p for p in output_dir.iterdir()
        if p.is_file() and GAME_FILE_RE.match(p.name)
    )


def parse_game_index(path: pathlib.Path) -> Optional[int]:
    m = GAME_FILE_RE.match(path.name)
    return int(m.group(1)) if m else None


def acquire_repair_lock(output_dir: pathlib.Path) -> pathlib.Path:
    """Acquire output_dir/.repair.lock. Aborts if another live invocation holds it."""
    lock_path = output_dir / ".repair.lock"
    if lock_path.exists():
        try:
            with lock_path.open() as f:
                info = json.load(f)
            holder_pid = int(info.get("pid", -1))
        except (json.JSONDecodeError, OSError, ValueError):
            holder_pid = -1

        if holder_pid > 0 and pid_alive(holder_pid):
            raise SystemExit(
                f"Another repair invocation is running (pid={holder_pid}). "
                f"If you're sure it's not, delete {lock_path}."
            )
        print(f"Found stale .repair.lock from pid={holder_pid}; removing.")
        lock_path.unlink()

    info = {"pid": os.getpid(), "timestamp": time.time()}
    with lock_path.open("w") as f:
        json.dump(info, f)
    return lock_path


def pid_alive(pid: int) -> bool:
    """Best-effort check whether a PID is still alive on the current OS."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in out.stdout
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def clean_orphan_locks(output_dir: pathlib.Path) -> int:
    """Remove game_NNNNNN.lock files with no corresponding .json. Returns count removed."""
    removed = 0
    for entry in output_dir.iterdir():
        m = LOCK_FILE_RE.match(entry.name)
        if not m:
            continue
        json_path = output_dir / f"game_{m.group(1)}.json"
        if not json_path.exists():
            entry.unlink()
            removed += 1
    return removed


def detect_bad_games(
    output_dir: pathlib.Path,
    only_indices: Optional[Set[int]] = None,
) -> Dict[int, Dict[int, List[str]]]:
    """Walk per-game JSONs and run check_game on each.

    Returns: {game_index: {ply: [error_strs]}} for games with any error.

    If only_indices is provided, only those games are checked (used on attempts > 1
    to avoid re-walking the entire output directory).
    """
    bad: Dict[int, Dict[int, List[str]]] = {}

    if only_indices is not None:
        targets = []
        for idx in sorted(only_indices):
            p = output_dir / f"game_{idx:06d}.json"
            if p.exists():
                targets.append(p)
            else:
                bad[idx] = {-1: ["game JSON missing after rerun"]}
    else:
        targets = find_game_files(output_dir)

    for path in targets:
        idx = parse_game_index(path)
        if idx is None:
            continue
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            bad[idx] = {-1: [f"unreadable JSON: {e}"]}
            continue

        if isinstance(data, dict) and "games" in data:
            game = data["games"][0] if data["games"] else {}
        else:
            game = data

        errors_by_ply = check_game(game)
        if errors_by_ply:
            bad[idx] = errors_by_ply

    return bad


def headers_match(
    pgn_path: pathlib.Path,
    bad_indices: Set[int],
    output_dir: pathlib.Path,
) -> Tuple[bool, List[str]]:
    """Verify PGN game at each bad index has headers matching the bad JSON.

    Returns (ok, mismatch_messages). Streams the PGN so this is O(N) reads but
    only header-deep (chess.pgn.read_headers is much cheaper than read_game).
    """
    needed = set(bad_indices)
    if not needed:
        return True, []

    expected: Dict[int, Dict[str, str]] = {}
    for idx in needed:
        json_path = output_dir / f"game_{idx:06d}.json"
        if not json_path.exists():
            continue
        try:
            with json_path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and "games" in data:
            data = data["games"][0] if data["games"] else {}
        expected[idx] = {
            "white": data.get("white", ""),
            "black": data.get("black", ""),
            "date": data.get("date", ""),
            "round": str(data.get("round", "")),
        }

    if not expected:
        return True, []

    max_idx = max(expected)
    mismatches: List[str] = []

    with pgn_path.open(encoding="latin-1") as f:
        idx = 0
        while idx < max_idx:
            headers = chess.pgn.read_headers(f)
            if headers is None:
                mismatches.append(
                    f"PGN ends at game {idx}; expected at least {max_idx} games."
                )
                break
            idx += 1
            if idx not in expected:
                continue
            exp = expected[idx]
            actual = {
                "white": headers.get("White", ""),
                "black": headers.get("Black", ""),
                "date": headers.get("Date", ""),
                "round": str(headers.get("Round", "")),
            }
            for key in ("white", "black", "date", "round"):
                if exp[key] != actual[key]:
                    mismatches.append(
                        f"Game {idx}: JSON has {key}={exp[key]!r}, "
                        f"PGN has {key}={actual[key]!r}"
                    )
                    break

    return not mismatches, mismatches


def quarantine_bad_games(
    output_dir: pathlib.Path,
    bad_indices: Set[int],
    attempt: int,
) -> int:
    """Move bad game JSONs to OUTPUT_DIR/quarantine/ with attempt suffix.

    Also removes any matching .lock files. Returns count moved.
    """
    quarantine = output_dir / "quarantine"
    quarantine.mkdir(exist_ok=True)
    moved = 0
    for idx in sorted(bad_indices):
        src = output_dir / f"game_{idx:06d}.json"
        if not src.exists():
            continue
        dst = quarantine / f"game_{idx:06d}.attempt{attempt}.json"
        shutil.move(str(src), str(dst))
        moved += 1
        lock = output_dir / f"game_{idx:06d}.lock"
        if lock.exists():
            lock.unlink()
    return moved


def detect_gpu_count() -> int:
    """Try nvidia-smi to count GPUs; default to 1 on failure."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--list-gpus"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            count = sum(1 for line in result.stdout.splitlines() if line.strip())
            return max(count, 1)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return 1


def run_workers(
    pgn_path: pathlib.Path,
    output_dir: pathlib.Path,
    gpus: int,
    forwarded_args: List[str],
) -> List[int]:
    """Spawn `gpus` analyze_pgn.py workers and wait for all to finish.

    Mirrors run_multi_gpu.sh: pins lc0 to GPU i via --lc0.backend-opts=gpu=i,
    sets --worker-id=GPU{i}, and writes per-worker logs to OUTPUT_DIR/GPU{i}.log.
    Returns a list of exit codes (one per worker).
    """
    analyze_script = pathlib.Path(__file__).resolve().parent / "analyze_pgn.py"
    dummy_output = output_dir / "unused.json"

    procs: List[Tuple[int, subprocess.Popen, "io.TextIOBase"]] = []  # noqa: F821
    log_handles = []

    for gpu in range(gpus):
        worker_id = f"GPU{gpu}"
        log_path = output_dir / f"{worker_id}.log"
        log_handle = log_path.open("w", encoding="utf-8")
        log_handles.append(log_handle)

        cmd = [
            sys.executable, "-u", str(analyze_script),
            str(pgn_path), str(dummy_output),
            f"--work-dir={output_dir}",
            f"--worker-id={worker_id}",
        ]
        if gpus > 1:
            cmd.append(f"--lc0.backend-opts=gpu={gpu}")
        cmd.extend(forwarded_args)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        print(f"  Launching {worker_id} -> {log_path.name}")
        proc = subprocess.Popen(
            cmd, stdout=log_handle, stderr=subprocess.STDOUT, env=env,
        )
        procs.append((gpu, proc, log_handle))

    print(f"  All {gpus} worker(s) launched. Waiting...")
    exit_codes = []
    try:
        for gpu, proc, _ in procs:
            rc = proc.wait()
            exit_codes.append(rc)
            if rc != 0:
                print(f"  WARNING: GPU{gpu} exited with code {rc}")
    except KeyboardInterrupt:
        print("\n  Interrupted; terminating workers...")
        for _, proc, _ in procs:
            try:
                proc.terminate()
            except OSError:
                pass
        for _, proc, _ in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        raise
    finally:
        for h in log_handles:
            h.close()

    return exit_codes


def print_bad_summary(bad: Dict[int, Dict[int, List[str]]]) -> None:
    if not bad:
        print("  No errors detected.")
        return
    counts: Dict[str, int] = {}
    for plies in bad.values():
        for errs in plies.values():
            for e in errs:
                counts[e] = counts.get(e, 0) + 1
    print(f"  Bad games: {len(bad)}")
    print(f"  Bad ply-error rows: {sum(counts.values())}")
    for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"    {cat}: {n}")


def write_repair_log(
    output_dir: pathlib.Path,
    history: List[Dict],
    final_bad: Dict[int, Dict[int, List[str]]],
    started_at: float,
) -> None:
    log_path = output_dir / "repair_log.json"
    total_repaired = sum(len(a["repaired"]) for a in history)
    payload = {
        "started_at": started_at,
        "duration_s": time.time() - started_at,
        "attempts": history,
        "summary": {
            "total_repaired": total_repaired,
            "persistent_failures": len(final_bad),
        },
    }
    with log_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(f"  Wrote {log_path}")


def write_failures_report(
    output_dir: pathlib.Path,
    final_bad: Dict[int, Dict[int, List[str]]],
    history: List[Dict],
) -> None:
    """List persistent-failure games with full per-attempt error history."""
    history_by_idx: Dict[int, List[Dict]] = {}
    for attempt in history:
        for idx, plies in attempt["errors"].items():
            history_by_idx.setdefault(int(idx), []).append({
                "attempt": attempt["n"],
                "errors_by_ply": plies,
            })
    payload = {
        "persistent_failures": [
            {
                "game_index": idx,
                "final_errors_by_ply": final_bad[idx],
                "history": history_by_idx.get(idx, []),
            }
            for idx in sorted(final_bad)
        ]
    }
    path = output_dir / "repair_failures.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(f"  Wrote {path}")


def parse_args(argv: List[str]) -> Tuple[argparse.Namespace, List[str]]:
    parser = argparse.ArgumentParser(
        description="Detect lc0 output errors, re-run affected games, verify, repeat.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Any extra arguments are forwarded verbatim to analyze_pgn.py — for example
--config=path, --search.nodes=2000, --lc0.backend=cuda-fp16. Do NOT pass
--work-dir, --worker-id, or the positional pgn/output args; the repair
script handles those.
""",
    )
    parser.add_argument("source_pgn", type=pathlib.Path,
                        help="Original PGN used for the run being repaired.")
    parser.add_argument("output_dir", type=pathlib.Path,
                        help="Work directory containing game_NNNNNN.json files.")
    parser.add_argument("--max-attempts", type=int, default=2,
                        help="Maximum re-run attempts (default: 2). Use 0 with "
                             "--dry-run for detect-only.")
    parser.add_argument("--gpus", type=int, default=None,
                        help="Number of GPU workers (default: nvidia-smi or 1).")
    parser.add_argument("--clean-quarantine", action="store_true",
                        help="On full clean success, remove the quarantine/ dir. "
                             "Default keeps it for inspection.")
    parser.add_argument("--no-pgn-validation", action="store_true",
                        help="Skip header-match check between bad JSONs and PGN. "
                             "Use only if you know the PGN is correct.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect bad games and print summary; do not "
                             "quarantine or re-run.")
    return parser.parse_known_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args, forwarded = parse_args(argv if argv is not None else sys.argv[1:])

    source_pgn: pathlib.Path = args.source_pgn
    output_dir: pathlib.Path = args.output_dir

    if not source_pgn.exists():
        print(f"ERROR: SOURCE_PGN not found: {source_pgn}", file=sys.stderr)
        return 2
    if not output_dir.is_dir():
        print(f"ERROR: OUTPUT_DIR is not a directory: {output_dir}", file=sys.stderr)
        return 2

    initial_files = find_game_files(output_dir)
    if not initial_files:
        print(
            f"ERROR: {output_dir} contains no game_NNNNNN.json files. "
            f"This looks like a merged-output directory, not a multi-GPU work-dir.",
            file=sys.stderr,
        )
        return 2

    print(f"Repair target: {output_dir} ({len(initial_files)} game files)")

    started_at = time.time()
    repair_lock = acquire_repair_lock(output_dir)

    try:
        orphans = clean_orphan_locks(output_dir)
        if orphans:
            print(f"Cleaned {orphans} orphan lock file(s).")

        gpus = args.gpus if args.gpus is not None else detect_gpu_count()
        if gpus < 1:
            gpus = 1
        print(f"Workers per attempt: {gpus}")

        history: List[Dict] = []
        last_bad_indices: Optional[Set[int]] = None  # None on attempt 1 -> full scan

        for attempt in range(1, args.max_attempts + 1):
            attempt_start = time.time()
            print(f"\n=== Attempt {attempt}/{args.max_attempts} ===")
            print("Detecting errors...")
            bad = detect_bad_games(output_dir, only_indices=last_bad_indices)
            print_bad_summary(bad)

            if not bad:
                print(f"\nAll clean after {attempt - 1} repair attempt(s).")
                history.append({
                    "n": attempt,
                    "repaired": [],
                    "still_bad": [],
                    "errors": {},
                    "duration_s": time.time() - attempt_start,
                })
                break

            if args.dry_run:
                print("\n--dry-run: stopping before quarantine. No changes made.")
                return 0

            bad_indices = set(bad.keys())

            if not args.no_pgn_validation:
                print("Validating PGN headers against bad JSONs...")
                ok, mismatches = headers_match(source_pgn, bad_indices, output_dir)
                if not ok:
                    print("ERROR: PGN does not match the JSONs being repaired:",
                          file=sys.stderr)
                    for m in mismatches[:10]:
                        print(f"  {m}", file=sys.stderr)
                    if len(mismatches) > 10:
                        print(f"  ... and {len(mismatches) - 10} more.",
                              file=sys.stderr)
                    print("Aborting. Pass --no-pgn-validation to override.",
                          file=sys.stderr)
                    return 3
                print("  PGN headers match.")

            moved = quarantine_bad_games(output_dir, bad_indices, attempt)
            print(f"Quarantined {moved} bad JSON(s).")

            print("Spawning workers to re-run missing games...")
            run_workers(source_pgn, output_dir, gpus, forwarded)

            history.append({
                "n": attempt,
                "repaired": sorted(bad_indices),
                "still_bad": [],  # filled in by next iteration's detect
                "errors": {str(k): v for k, v in bad.items()},
                "duration_s": time.time() - attempt_start,
            })
            last_bad_indices = bad_indices  # next iteration only re-checks these

        print("\n=== Final verification ===")
        final_bad = detect_bad_games(output_dir, only_indices=last_bad_indices)
        print_bad_summary(final_bad)

        if history and history[-1].get("repaired"):
            history[-1]["still_bad"] = sorted(final_bad.keys())

        write_repair_log(output_dir, history, final_bad, started_at)

        if final_bad:
            print(
                f"\n{len(final_bad)} game(s) still failing after "
                f"{args.max_attempts} attempt(s).",
                file=sys.stderr,
            )
            write_failures_report(output_dir, final_bad, history)
            print(
                "Bad JSONs left in OUTPUT_DIR (not quarantined) so they remain "
                "visible to convert_json_to_parquet.py. Inspect "
                "repair_failures.json and decide whether to delete or keep.",
                file=sys.stderr,
            )
            return 1

        print("\nClean. Ready for convert_json_to_parquet.py.")
        if args.clean_quarantine:
            quarantine = output_dir / "quarantine"
            if quarantine.is_dir():
                shutil.rmtree(quarantine)
                print(f"Removed {quarantine}")
        return 0

    finally:
        try:
            repair_lock.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    sys.exit(main())
