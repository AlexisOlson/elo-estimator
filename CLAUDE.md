# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A pipeline that runs Leela Chess Zero (lc0) over PGN files and emits per-position move-quality data, used downstream for ML-based Elo estimation. `README.md` covers the goal, lc0 rationale, output schema, and build/install steps — start there. This file covers the things README doesn't: who the data is for, conventions agreed with collaborators, the multi-GPU production pipeline, and points where the in-repo docs have drifted from reality.

## Collaborators and deliverable shape

Two end users consume the lc0 output for parallel projects:
- **Jeff Sonas** (Chessmetrics) — primary user. Calibrates historical Chessmetrics ratings to a modern absolute Elo scale. Drives the dataset asks.
- **Mark Glickman** (Glicko / Glickman ratings) — secondary user. Building a moves-based rating system off the same data.

Conventions agreed with them (not in code/docs):
- **Deliverable**: a three-CSV bundle — `games.csv`, `plies.csv`, `candidate_moves.csv`, zipped — uploaded to a shared Google Drive "Elo Estimator" folder. `convert_json_to_parquet.py` (at repo root) produces this; pass `--csv` for CSV-only or omit flags for both Parquet and CSV.
- **Move ordering**: pipeline output ranks candidates by Leela's native order (visits → Q-value → policy). Jeff and Mark both re-rank by Q-value in their own SQL/analysis layer (Mark is probability-based, Jeff follows). Don't change the output ordering without an explicit ask — the `rank` field is part of the consumed schema.
- **Variance signal**: keep `u_value` and `visits` in output so downstream can model evaluation confidence.
- **Jeff's tooling constraint**: SQL Server 2017 (homeschool license). He ingests via CSV + `BULK INSERT` with row line numbers for ordering. He has no `OPENROWSET`/Parquet path. Parquet output is fine for our own analysis but not for him.

Communication is via Discord. Don't put PII (Discord handles, payment details, Drive URLs) in committed files; those live in this project's local memory directory under `.claude/projects/C--elo-estimator/memory/`.

## Run configuration the docs don't always reflect

The production runs (Jan 2026, 190K games + ongoing top-ups) use settings that differ from what's currently checked in:

| Setting | `config/lc0_config.json` (committed) | Production reality |
|---|---|---|
| `search.value` (nodes/ply) | 1000 | **2000** |
| `max_candidates` | 20 | 20 |
| MLH bias | not set | **disabled** (threshold=1, max_bonus=0) — set in `extra_args` |
| Backend | `cuda-fp16` | same |
| Network | BT4 1024x15x32h | same (`networks/BT4-1024x15x32h-swa-6147500.pb.gz`) |

`config/lc0_config.vastai.json` is closer to production (2000 nodes, container paths). When kicking off a real run, override on the command line (`--search.nodes=2000`) rather than mutating the committed config — see `scripts/README.md` for the override syntax (positional args first; `--search.nodes=N`, not `--nodes`).

`docs/config_example.md` says `max_candidates` defaults to 10 — that conflicts with the actual config (20). Trust the JSON when in doubt.

## Multi-GPU is the production path

`scripts/run_multi_gpu.sh` is how full datasets are run, not direct invocation of `analyze_pgn.py`. Each GPU worker claims games via `.lock` files in a shared `--output-dir`; one JSON per game is written. `--start-index=N` resumes from a given game (used when an interruptible vast.ai instance gets outbid). Docs: `docs/MULTI_GPU_USAGE.md` and `VASTAI_USAGE.md`.

`docs/archive/multi_gpu_plan.md` is a historical planning doc — the cherry-picks from `archive-experiments` it describes are already done on the `multi-gpu` branch. Don't follow it as a TODO list.

## Error philosophy

About 0.17% of games hit non-reproducible artifacts from lc0's internal batch parallelism — one or more plies show truncated VerboseMoveStats, missing q-values, zero-visit candidates, or played moves not in the candidate list. Total visits less than ~1990 reliably flags a suspect ply.

These do not reproduce on rerun. Don't chase them in lc0; just rerun the affected games and merge. The four error categories Jeff catches in his SQL queries:

1. played move not evaluated
2. played move not in candidate moves
3. candidate moves include 0 visits
4. candidate moves include blank eval(s)

Two tools:
- `scripts/check_errors.py <dir-or-file>` validates output. Pass `--csv errors.csv` to dump per-ply errors.
- `scripts/repair_errors.py SOURCE_PGN OUTPUT_DIR` automates the full detect → quarantine → re-run → re-verify loop against a multi-GPU work-dir. Default `--max-attempts=2`. Persistent failures are listed in `OUTPUT_DIR/repair_failures.json` and bad JSONs are left in place (not quarantined) so they stay visible to `convert_json_to_parquet.py`. Use `--dry-run` for detect-only.

## Common commands

```powershell
# Setup (Windows)
.\scripts\setup_venv.ps1
.\.venv\Scripts\Activate.ps1

# Single-game smoke test
python scripts\analyze_pgn.py pgn-data\samples\single.pgn output\test.json --search.nodes=100

# Full multi-GPU run (Linux/container; the .sh script is bash)
./scripts/run_multi_gpu.sh /path/to/games.pgn --output-dir=output/run --search.nodes=2000

# Resume an interrupted run
./scripts/run_multi_gpu.sh /path/to/games.pgn --output-dir=output/run --start-index=65001

# Validate output against Jeff's four error categories
python scripts\check_errors.py output\run\ --csv errors.csv

# Auto-repair: detect errors, re-run affected games, verify, repeat
python scripts\repair_errors.py path\to\source.pgn output\run\

# Build the deliverable bundle (zipped CSVs + Parquet)
python convert_json_to_parquet.py output\run\ output\bundle\
```

## Documentation alignment

As of v1.5.0, `README.md`, `CHANGELOG.md`, `docs/config_example.md`, and `docs/output_format.json` reflect the actual production config. Planning docs in `docs/archive/` are historical and not authoritative. When changing production defaults (e.g., `lc0_config.json`), update the user-facing docs in the same commit; treat `README.md` and `CHANGELOG.md` as the load-bearing surface.
