#!/usr/bin/env python3
"""Check JSON output for the 4 error types identified by Jeff Sonas.

Error types:
1. 'played move not evaluated' - evaluation field missing or incomplete
2. 'played move not in candidate moves' - played move not found in candidate_moves
3. 'candidate moves include 0 visits' - any candidate has visits=0
4. 'candidate moves include blank eval(s)' - any candidate missing WDL/Q/policy
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def check_position(pos: Dict[str, Any], ply: int) -> List[str]:
    """Check a single position for errors. Returns list of error types found."""
    errors = []

    evaluation = pos.get("evaluation")
    candidate_moves = pos.get("candidate_moves", [])
    played_move = pos.get("played_move")

    # Error 1: played move not evaluated
    if not evaluation:
        errors.append("played move not evaluated")
    else:
        # Check if evaluation has required fields (uses q_value not Q)
        required_eval_fields = ["visits", "q_value", "wdl"]
        if any(evaluation.get(f) is None for f in required_eval_fields):
            errors.append("played move not evaluated")

    # Error 2: played move not in candidate moves
    if played_move and candidate_moves:
        candidate_sans = [c.get("move") for c in candidate_moves]
        if played_move not in candidate_sans:
            errors.append("played move not in candidate moves")

    # Error 3: candidate moves include 0 visits
    for candidate in candidate_moves:
        if candidate.get("visits", -1) == 0:
            errors.append("candidate moves include 0 visits")
            break

    # Error 4: candidate moves include blank eval(s)
    for candidate in candidate_moves:
        wdl = candidate.get("wdl")
        q = candidate.get("q_value")
        policy = candidate.get("policy")
        if wdl is None or q is None or policy is None:
            errors.append("candidate moves include blank eval(s)")
            break

    return errors


def check_game(game_data: Dict[str, Any]) -> Dict[int, List[str]]:
    """Check all positions in a game. Returns dict of ply -> errors."""
    errors_by_ply = {}

    # Use 'moves' array (not 'positions')
    moves = game_data.get("moves", [])
    for pos in moves:
        ply = pos.get("ply", 0)
        errors = check_position(pos, ply)
        if errors:
            errors_by_ply[ply] = errors

    return errors_by_ply


def main():
    parser = argparse.ArgumentParser(description="Check JSON output for analysis errors")
    parser.add_argument("path", help="JSON file or directory of JSON files to check")
    parser.add_argument("--summary", action="store_true", help="Show summary only")
    parser.add_argument("--csv", help="Output errors to CSV file")
    args = parser.parse_args()

    json_path = Path(args.path)
    if not json_path.exists():
        print(f"Error: Path not found: {json_path}")
        sys.exit(1)

    # Collect all JSON files
    if json_path.is_dir():
        json_files = sorted(json_path.glob("*.json"))
        if not json_files:
            print(f"Error: No JSON files found in {json_path}")
            sys.exit(1)
        print(f"Found {len(json_files)} JSON files in {json_path}")
    else:
        json_files = [json_path]

    # Load all games
    games = []
    for jf in json_files:
        with open(jf) as f:
            data = json.load(f)
        # Handle different JSON structures:
        # 1. {"games": [...]} wrapper
        # 2. Array of games [...]
        # 3. Single game {...}
        if isinstance(data, dict) and "games" in data:
            games.extend(data["games"])
        elif isinstance(data, list):
            games.extend(data)
        else:
            games.append(data)

    # Track error counts
    error_counts = {
        "played move not evaluated": 0,
        "played move not in candidate moves": 0,
        "candidate moves include 0 visits": 0,
        "candidate moves include blank eval(s)": 0,
    }

    csv_rows = []
    games_with_errors = 0

    for game_idx, game in enumerate(games):
        game_id = game.get("game_index", game.get("site", game_idx))
        errors_by_ply = check_game(game)

        if errors_by_ply:
            games_with_errors += 1

            if not args.summary:
                print(f"\nGame {game_id}:")

            for ply, errors in sorted(errors_by_ply.items()):
                for error in errors:
                    error_counts[error] += 1
                    csv_rows.append({
                        "game_index": game_id,
                        "ply": ply,
                        "error_type": error
                    })

                if not args.summary:
                    print(f"  Ply {ply}: {', '.join(errors)}")

    # Print summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    print(f"Total games checked: {len(games)}")
    print(f"Games with errors: {games_with_errors}")
    print()
    print("Error counts:")
    for error_type, count in error_counts.items():
        print(f"  {error_type}: {count}")

    # Write CSV if requested
    if args.csv:
        import csv
        with open(args.csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["game_index", "ply", "error_type"])
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"\nErrors written to: {args.csv}")


if __name__ == "__main__":
    main()
