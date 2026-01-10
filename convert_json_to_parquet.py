"""
Convert chess game JSON files to Parquet and CSV formats.

Creates three tables:
- games: One row per game (metadata)
- plies: One row per ply/position
- candidate_moves: One row per candidate move

Usage:
    python convert_json_to_parquet.py <input_dir> <output_dir> [--csv] [--parquet]

Options:
    --csv       Output CSV files (zipped)
    --parquet   Output Parquet files
    (default: both if neither specified)
"""

import sys
import json
import zipfile
from pathlib import Path
import polars as pl
import gc


def process_game_file(file_path: Path) -> tuple[dict, list[dict], list[dict]]:
    """Process a single JSON game file and return game, plies, and candidate moves data."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    game_index = data["game_index"]

    # Game-level data
    game_row = {
        "game_index": game_index,
        "event": data.get("event", ""),
        "site": data.get("site", ""),
        "date": data.get("date", ""),
        "round": data.get("round", ""),
        "white": data.get("white", ""),
        "white_elo": data.get("white_elo"),
        "black": data.get("black", ""),
        "black_elo": data.get("black_elo"),
        "result": data.get("result", ""),
        "eco": data.get("eco", ""),
    }

    ply_rows = []
    candidate_rows = []

    for move in data.get("moves", []):
        ply = move["ply"]
        eval_data = move.get("evaluation", {})

        # Ply-level data
        ply_row = {
            "game_index": game_index,
            "ply": ply,
            "fen": move.get("fen", ""),
            "to_move": move.get("to_move", ""),
            "total_legal_moves": move.get("total_legal_moves"),
            "total_visits": move.get("total_visits"),
            "visits_on_better": move.get("visits_on_better"),
            "played_move": move.get("played_move", ""),
            # Flatten evaluation
            "rank": eval_data.get("rank"),
            "visits": eval_data.get("visits"),
            "P": eval_data.get("policy"),
            "Q": eval_data.get("q_value"),
            "U": eval_data.get("u_value"),
            "wdl_w": eval_data.get("wdl", [None, None, None])[0],
            "wdl_d": eval_data.get("wdl", [None, None, None])[1],
            "wdl_l": eval_data.get("wdl", [None, None, None])[2],
        }
        ply_rows.append(ply_row)

        # Candidate moves data
        for candidate in move.get("candidate_moves", []):
            wdl = candidate.get("wdl", [None, None, None])
            candidate_row = {
                "game_index": game_index,
                "ply": ply,
                "move": candidate.get("move", ""),
                "rank": candidate.get("rank"),
                "visits": candidate.get("visits"),
                "P": candidate.get("policy"),
                "Q": candidate.get("q_value"),
                "U": candidate.get("u_value"),
                "wdl_w": wdl[0] if len(wdl) > 0 else None,
                "wdl_d": wdl[1] if len(wdl) > 1 else None,
                "wdl_l": wdl[2] if len(wdl) > 2 else None,
            }
            candidate_rows.append(candidate_row)

    return game_row, ply_rows, candidate_rows


def make_games_df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows).cast({
        "game_index": pl.Int32,
        "white_elo": pl.Int16,
        "black_elo": pl.Int16,
    })


def make_plies_df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows).cast({
        "game_index": pl.Int32,
        "ply": pl.Int16,
        "total_legal_moves": pl.Int8,
        "total_visits": pl.Int32,
        "visits_on_better": pl.Int32,
        "rank": pl.Int8,
        "visits": pl.Int32,
        "P": pl.Float32,
        "Q": pl.Float32,
        "U": pl.Float32,
        "wdl_w": pl.Int16,
        "wdl_d": pl.Int16,
        "wdl_l": pl.Int16,
    })


def make_candidates_df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows).cast({
        "game_index": pl.Int32,
        "ply": pl.Int16,
        "rank": pl.Int8,
        "visits": pl.Int32,
        "P": pl.Float32,
        "Q": pl.Float32,
        "U": pl.Float32,
        "wdl_w": pl.Int16,
        "wdl_d": pl.Int16,
        "wdl_l": pl.Int16,
    })


def zip_csv(csv_path: Path, zip_path: Path) -> tuple[int, int]:
    """Zip a CSV file with maximum compression, return (csv_size, zip_size)."""
    csv_size = csv_path.stat().st_size
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(csv_path, csv_path.name)
    zip_size = zip_path.stat().st_size
    csv_path.unlink()
    return csv_size, zip_size


def convert_games(input_dir: str, output_dir: str, output_csv: bool = True, output_parquet: bool = True, batch_size: int = 5000):
    """Convert all JSON game files to Parquet and/or CSV format using batched processing."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    json_files = list(input_path.glob("game_*.json"))
    total_files = len(json_files)
    print(f"Found {total_files:,} JSON files to process")
    print(f"Processing in batches of {batch_size:,}")

    # Temp directory for batch files
    temp_path = output_path / "_temp_batches"
    temp_path.mkdir(exist_ok=True)

    batch_num = 0
    total_games = 0
    total_plies = 0
    total_candidates = 0

    for batch_start in range(0, total_files, batch_size):
        batch_end = min(batch_start + batch_size, total_files)
        batch_files = json_files[batch_start:batch_end]

        all_games = []
        all_plies = []
        all_candidates = []

        for file_path in batch_files:
            try:
                game_row, ply_rows, candidate_rows = process_game_file(file_path)
                all_games.append(game_row)
                all_plies.extend(ply_rows)
                all_candidates.extend(candidate_rows)
            except Exception as e:
                print(f"Error processing {file_path.name}: {e}")
                continue

        total_games += len(all_games)
        total_plies += len(all_plies)
        total_candidates += len(all_candidates)

        # Write batch to temp parquet files
        games_df = make_games_df(all_games)
        plies_df = make_plies_df(all_plies)
        candidates_df = make_candidates_df(all_candidates)

        games_df.write_parquet(temp_path / f"games_{batch_num:04d}.parquet")
        plies_df.write_parquet(temp_path / f"plies_{batch_num:04d}.parquet")
        candidates_df.write_parquet(temp_path / f"candidates_{batch_num:04d}.parquet")

        # Free memory
        del all_games, all_plies, all_candidates
        del games_df, plies_df, candidates_df
        gc.collect()

        batch_num += 1
        print(f"Processed {batch_end:,} / {total_files:,} files ({batch_end / total_files * 100:.1f}%)")

    print(f"\nTotal rows:")
    print(f"  Games: {total_games:,}")
    print(f"  Plies: {total_plies:,}")
    print(f"  Candidate moves: {total_candidates:,}")

    # Combine batch files into final output
    print(f"\nCombining {batch_num} batches...")

    total_size = 0

    # Games
    print("  Combining games...")
    games_df = pl.concat([pl.read_parquet(f) for f in sorted(temp_path.glob("games_*.parquet"))])
    if output_parquet:
        games_path = output_path / "games.parquet"
        games_df.write_parquet(games_path, compression="zstd", compression_level=9)
        print(f"    games.parquet: {games_path.stat().st_size / 1024 / 1024:.2f} MB")
        total_size += games_path.stat().st_size
    if output_csv:
        csv_path = output_path / "games.csv"
        games_df.write_csv(csv_path)
        csv_size, zip_size = zip_csv(csv_path, output_path / "games.csv.zip")
        print(f"    games.csv.zip: {zip_size / 1024 / 1024:.2f} MB (uncompressed: {csv_size / 1024 / 1024:.2f} MB)")
        total_size += zip_size
    del games_df
    gc.collect()

    # Plies
    print("  Combining plies...")
    plies_df = pl.concat([pl.read_parquet(f) for f in sorted(temp_path.glob("plies_*.parquet"))])
    if output_parquet:
        plies_path = output_path / "plies.parquet"
        plies_df.write_parquet(plies_path, compression="zstd", compression_level=9)
        print(f"    plies.parquet: {plies_path.stat().st_size / 1024 / 1024:.2f} MB")
        total_size += plies_path.stat().st_size
    if output_csv:
        csv_path = output_path / "plies.csv"
        plies_df.write_csv(csv_path)
        csv_size, zip_size = zip_csv(csv_path, output_path / "plies.csv.zip")
        print(f"    plies.csv.zip: {zip_size / 1024 / 1024:.2f} MB (uncompressed: {csv_size / 1024 / 1024:.2f} MB)")
        total_size += zip_size
    del plies_df
    gc.collect()

    # Candidates
    print("  Combining candidate moves...")
    candidates_df = pl.concat([pl.read_parquet(f) for f in sorted(temp_path.glob("candidates_*.parquet"))])
    if output_parquet:
        candidates_path = output_path / "candidate_moves.parquet"
        candidates_df.write_parquet(candidates_path, compression="zstd", compression_level=9)
        print(f"    candidate_moves.parquet: {candidates_path.stat().st_size / 1024 / 1024:.2f} MB")
        total_size += candidates_path.stat().st_size
    if output_csv:
        csv_path = output_path / "candidate_moves.csv"
        candidates_df.write_csv(csv_path)
        csv_size, zip_size = zip_csv(csv_path, output_path / "candidate_moves.csv.zip")
        print(f"    candidate_moves.csv.zip: {zip_size / 1024 / 1024:.2f} MB (uncompressed: {csv_size / 1024 / 1024:.2f} MB)")
        total_size += zip_size
    del candidates_df
    gc.collect()

    # Cleanup temp files
    print("\nCleaning up temp files...")
    for f in temp_path.glob("*.parquet"):
        f.unlink()
    temp_path.rmdir()

    print(f"\nTotal output size: {total_size / 1024 / 1024:.2f} MB")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]

    # Parse flags
    args = sys.argv[3:]
    output_csv = "--csv" in args
    output_parquet = "--parquet" in args

    # Default to both if neither specified
    if not output_csv and not output_parquet:
        output_csv = True
        output_parquet = True

    convert_games(input_dir, output_dir, output_csv=output_csv, output_parquet=output_parquet)
    print("\nDone!")


if __name__ == "__main__":
    main()
