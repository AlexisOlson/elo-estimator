#!/usr/bin/env python3
"""Analyze PGN positions with lc0, writing SAN notation directly (no temp files).

This script analyzes chess games using Leela Chess Zero (lc0) and outputs structured
JSON with comprehensive move evaluations.

Key Features:
1. Loads lc0 execution parameters from a JSON config file
2. Reads positions from a PGN file
3. Sends each position to lc0 via UCI protocol
4. Parses lc0 output (MultiPV + VerboseMoveStats) and converts UCI to SAN
5. Handles played moves outside top-N candidates with focused searches
6. Calculates move rankings across ALL legal moves (not just MultiPV)
7. Writes complete JSON records with no intermediate files

Output Fields:
- total_visits: Sum of visits across all legal moves (≈ node budget)
- visits_on_better: Visits on moves ranked better than played (0 if rank 1)
- evaluation: Rank, visits, policy, Q-value, WDL for the played move
- candidate_moves: Top N moves with rank, visits, policy, Q-value, WDL

Bug Fixes Applied:
- Evaluation now shows played move data (not best move data)
- Moves outside MultiPV are analyzed with focused search for WDL
- Rankings recalculated from VerboseMoveStats to match LC0's final state
- Rankings use same criteria as LC0: visits > Q-value > policy
- All fields always present (no disappearing fields)
"""

import argparse
import json
import pathlib
import subprocess
import sys
import re
from typing import Any, Dict, List, Optional, Tuple

import chess
import chess.pgn


def _compact_json_dumps(obj: Any, indent: int = 2) -> str:
    """Serialize obj to JSON with compact formatting for specific structures.
    
    Compact formats:
    - WDL arrays: [w, d, l] on single line
    - evaluation objects: entire object on single line
    - candidate_moves array items: each move object on single line
    """
    # First pass: standard JSON with indentation
    json_str = json.dumps(obj, indent=indent)
    
    # Compact WDL arrays: [w, d, l]
    wdl_pattern = r'\[\s*(\d+),\s*(\d+),\s*(\d+)\s*\]'
    json_str = re.sub(wdl_pattern, r'[\1, \2, \3]', json_str)
    
    # Compact evaluation objects to single line
    # Pattern: "evaluation": {\n      fields...\n    }
    # Capture indentation before "evaluation" to preserve it
    eval_pattern = r'(\s*)"evaluation":\s*\{\s*([^}]+?)\s*\}'
    def compact_eval(match):
        leading_indent = match.group(1)
        fields = match.group(2)
        # Remove newlines and compress multiple spaces to single space
        fields_compact = re.sub(r'\s+', ' ', fields).strip()
        # Format on same line as "evaluation":
        return f'{leading_indent}"evaluation": {{{fields_compact}}}'
    json_str = re.sub(eval_pattern, compact_eval, json_str, flags=re.DOTALL)
    
    # Compact candidate_moves arrays with aligned decimal points and commas
    lines = json_str.split('\n')
    result_lines = []
    line_idx = 0
    
    while line_idx < len(lines):
        if '"candidate_moves":' not in lines[line_idx]:
            result_lines.append(lines[line_idx])
            line_idx += 1
            continue
            
        result_lines.append(lines[line_idx])
        line_idx += 1
        
        # Parse candidate objects and their fields
        candidates = []
        while line_idx < len(lines) and lines[line_idx].strip() not in (']', '],'):
            if lines[line_idx].strip() != '{':
                line_idx += 1
                continue
                
            indent = len(lines[line_idx]) - len(lines[line_idx].lstrip())
            line_idx += 1
            fields = {}
            while line_idx < len(lines) and '}' not in lines[line_idx]:
                if '":' in lines[line_idx] and (parts := lines[line_idx].strip().rstrip(',').split('":', 1)):
                    fields[parts[0].strip('"')] = parts[1].strip()
                line_idx += 1
            candidates.append((indent, fields, lines[line_idx].strip()))
            line_idx += 1
        
        # Calculate max widths by field type
        widths = {}
        for _, fields, _ in candidates:
            for k, v in fields.items():
                if k == "move":
                    widths[k] = max(widths.get(k, 0), len(v.strip('"')))
                elif k == "wdl" and (m := re.match(r'\[(\d+),\s*(\d+),\s*(\d+)\]', v)):
                    for idx, s in enumerate(['w', 'd', 'l'], 1):
                        widths[f'wdl_{s}'] = max(widths.get(f'wdl_{s}', 0), len(m.group(idx)))
                elif k in ["policy", "q_value"] and '.' in v:
                    int_p, dec_p = v.split('.', 1)
                    widths[f'{k}_i'] = max(widths.get(f'{k}_i', 0), len(int_p))
                    widths[f'{k}_d'] = max(widths.get(f'{k}_d', 0), len(dec_p))
                else:
                    widths[k] = max(widths.get(k, 0), len(v))
        
        # Format candidates with padding
        for indent, fields, closing in candidates:
            parts = []
            for k, v in fields.items():
                if k == "move":
                    # Pad the move string itself (not with trailing spaces, but with spaces after the quote)
                    move_str = v.strip('"')
                    parts.append(f'"{k}": "{move_str}"{" " * (widths[k] - len(move_str))}')
                elif k == "wdl" and (m := re.match(r'\[(\d+),\s*(\d+),\s*(\d+)\]', v)):
                    w, d, l = (m.group(idx).rjust(widths[f'wdl_{s}']) for idx, s in [(1,'w'), (2,'d'), (3,'l')])
                    parts.append(f'"{k}": [{w}, {d}, {l}]')
                elif k in ["policy", "q_value"] and '.' in v:
                    int_p, dec_p = v.split('.', 1)
                    parts.append(f'"{k}": {int_p.rjust(widths[f"{k}_i"])}.{dec_p.ljust(widths[f"{k}_d"])}')
                else:
                    parts.append(f'"{k}": {v:>{widths.get(k, len(v))}}')
            result_lines.append(' ' * indent + '{ ' + ', '.join(parts) + ' }' + (',' if closing == '},' else ''))
        
        if line_idx < len(lines):
            result_lines.append(lines[line_idx])
            line_idx += 1
    
    return '\n'.join(result_lines)


# Regex patterns
MULTIPV_RE = re.compile(r"multipv (\d+)")
WDL_RE = re.compile(r"wdl (\d+) (\d+) (\d+)")
PV_RE = re.compile(r" pv (.+)$")

# Regex for parsing verbose move stats (info string lines)
INFO_STRING_RE = re.compile(
    r"info string ([a-h][1-8][a-h][1-8][qrbn]?)"  # move in UCI
    r".*?"  # anything
    r"N:\s+(\d+)"  # visits
    r".*?"  # anything
    r"\(P:\s+([\d.]+)%\)"  # policy
    r".*?"  # anything
    r"\(Q:\s+([-\d.]+)\)"  # Q-value
)


def analyze_pgn(
    config: Dict[str, Any],
    pgn_path: pathlib.Path,
    output_path: pathlib.Path,
):
    """Analyze PGN file with lc0 and write SAN output directly."""
    
    lc0_path = pathlib.Path(config["lc0_path"])
    network_path = pathlib.Path(config["weights"])
    options: Dict[str, Any] = config.get("options", {})
    search_cfg: Dict[str, Any] = config.get("search", {})
    search_type = str(search_cfg.get("type", "nodes"))
    search_value = int(search_cfg.get("value", 100))
    max_candidates = int(config.get("max_candidates", options.get("MultiPV", config.get("multipv", 10))) or 10)
    multipv = int(options.get("MultiPV", config.get("multipv", max_candidates)))
    extra_args: List[str] = list(map(str, config.get("extra_args", [])))

    # Read PGN games
    games = []
    with pgn_path.open() as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            games.append(game)
    
    if not games:
        print("No games found in PGN!", file=sys.stderr)
        return
    
    print(f"Found {len(games)} game(s) in PGN")
    
    # Start lc0 in UCI mode
    lc0_cmd = [
        str(lc0_path),
        f"--weights={network_path}",
        *extra_args,
    ]
    
    process = subprocess.Popen(
        lc0_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    
    def send_command(cmd: str):
        """Send UCI command to lc0."""
        process.stdin.write(cmd + "\n")
        process.stdin.flush()
    
    def read_until(marker: str) -> List[str]:
        """Read lines until marker is found."""
        lines = []
        while True:
            line = process.stdout.readline().strip()
            lines.append(line)
            if marker in line:
                break
        return lines
    
    # Initialize UCI
    send_command("uci")
    read_until("uciok")
    if "VerboseMoveStats" not in options:
        options["VerboseMoveStats"] = True
    if "UCI_ShowWDL" not in options:
        options["UCI_ShowWDL"] = True
    if "MultiPV" not in options:
        options["MultiPV"] = multipv

    for opt_name, opt_value in options.items():
        send_command(f"setoption name {opt_name} value {_stringify_option(opt_value)}")
    send_command("isready")
    read_until("readyok")
    
    # Collect all game data
    all_games = []
    
    # Open output file for incremental writing
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_file = output_path.open("w", encoding="utf-8")
    out_file.write('{\n  "games": [\n')
    out_file.flush()
    
    # Helper function to write a single game incrementally
    def write_game(game_record, is_first):
        """Write a single game to the output file."""
        if not is_first:
            out_file.write(',\n')
        json_str = _compact_json_dumps(game_record, indent=2)
        # Indent the entire game object by 4 spaces
        indented = '\n'.join('    ' + line if line else line for line in json_str.split('\n'))
        out_file.write(indented)
        out_file.flush()
    
    try:
        # Analyze each game
        for game_idx, game in enumerate(games):
            white_player = game.headers.get("White", "")
            black_player = game.headers.get("Black", "")
            white_elo = _parse_elo(game.headers.get("WhiteElo"))
            black_elo = _parse_elo(game.headers.get("BlackElo"))
            
            event = game.headers.get("Event", "")
            date = game.headers.get("Date", "")
            site = game.headers.get("Site", "")
            round_num = game.headers.get("Round", "")
            result = game.headers.get("Result", "*")
            eco = game.headers.get("ECO", "")
            
            board = game.board()
            ply = 1
            moves = []

            # Prepare moves list so we know total plies for nicer tick output
            moves_list = list(game.mainline_moves())
            total_plies = len(moves_list)

            # Print game header (kept as a normal print). Per-ply ticking below is flushed.
            print(f"Analyzing game {game_idx + 1} ({total_plies} plies)...")

            for move_idx, move in enumerate(moves_list, start=1):
                fen = board.fen()
                to_move = "white" if board.turn == chess.WHITE else "black"
                played_move_san = board.san(move)

                # Print a short ticking status for each ply
                print(f"  Game {game_idx + 1} ply {move_idx}/{total_plies}: {played_move_san}", end='\r', flush=True)
                
                # Send position to lc0
                send_command(f"position fen {fen}")
                send_command(f"go {search_type} {search_value}")
                
                # Read analysis output
                lines = read_until("bestmove")
                
                # Parse candidate moves and evaluation
                candidates, evaluation, total_visits, visits_on_better = parse_analysis(lines, board, max_candidates, played_move_san)
                
                # If played move has no WDL (wasn't in MultiPV), do a focused search
                if evaluation and "wdl" not in evaluation:
                    # Run MultiPV=1 search with searchmoves restricted to played move
                    move_uci = board.uci(move)
                    send_command(f"position fen {fen}")
                    send_command(f"go {search_type} {search_value} searchmoves {move_uci}")
                    focused_lines = read_until("bestmove")
                    
                    # Extract WDL from this focused search
                    for line in focused_lines:
                        if "wdl" in line:
                            wdl_match = WDL_RE.search(line)
                            if wdl_match:
                                w, d, l = map(int, wdl_match.groups())
                                evaluation["wdl"] = [w, d, l]
                                
                                # Also update the candidate in candidates list if it exists
                                for candidate in candidates:
                                    if candidate["move"] == played_move_san:
                                        candidate["wdl"] = [w, d, l]
                                        break
                                break
                
                # Build move record
                move_record = {
                    "ply": ply,
                    "fen": fen,
                    "to_move": to_move,
                }
                
                # Always include total_visits and visits_on_better if we have verbose data
                if total_visits is not None:
                    move_record["total_visits"] = total_visits
                
                if visits_on_better is not None:
                    move_record["visits_on_better"] = visits_on_better
                
                move_record["played_move"] = played_move_san
                
                if evaluation:
                    move_record["evaluation"] = evaluation
                
                if candidates:
                    move_record["candidate_moves"] = candidates
                
                moves.append(move_record)
                
                # Make move and continue
                board.push(move)
                ply += 1
            
            print(f"  Analyzed {ply - 1} positions")
            
            # Build game record with metadata and moves
            game_record = {
                "game_index": game_idx + 1,
                "event": event,
                "site": site,
                "date": date,
                "round": round_num,
                "white": white_player,
                "white_elo": white_elo,
                "black": black_player,
                "black_elo": black_elo,
                "result": result,
                "eco": eco,
                "moves": moves,
            }
            all_games.append(game_record)
            
            # Write game incrementally
            write_game(game_record, is_first=(game_idx == 0))
            print(f"  Progress saved ({game_idx + 1}/{len(games)} games completed)")
    
    finally:
        # Close the JSON structure
        out_file.write('\n  ]\n}\n')
        out_file.close()
    
    # Cleanup
    send_command("quit")
    process.wait()
    
    print(f"\nDone! Output written to {output_path}")


def parse_analysis(lines: List[str], board: chess.Board, max_candidates: int, played_move_san: str) -> Tuple[List[Dict], Optional[Dict], Optional[int], Optional[int]]:
    """Parse lc0 output into candidate moves and evaluation.
    
    Args:
        lines: lc0 output lines
        board: Current chess position
        max_candidates: Maximum number of candidate moves to return
        played_move_san: The move that was actually played (in SAN notation)
    
    Returns:
        (candidates, evaluation, total_visits, visits_on_better) where:
        - candidates: List of candidate move dicts with rank, visits, wdl, policy, q_value
        - evaluation: Dict with evaluation for the played move (visits, wdl, policy, q_value)
        - total_visits: Sum of visits across ALL legal moves (should ≈ node budget)
        - visits_on_better: Sum of visits on moves ranked strictly better (0 if rank 1)
    """
    # Parse multipv lines for basic move info and WDL
    multipv_data = {}
    
    for line in lines:
        if "multipv" not in line:
            continue

        multipv_match = MULTIPV_RE.search(line)
        pv_match = PV_RE.search(line)
        wdl_match = WDL_RE.search(line)

        # Need at least multipv and pv
        if not (multipv_match and pv_match):
            continue

        pv_moves = pv_match.group(1).split()
        if not pv_moves:
            continue

        move_uci = pv_moves[0]

        # Convert UCI to SAN
        try:
            move_obj = chess.Move.from_uci(move_uci)
            if move_obj in board.legal_moves:
                move_san = board.san(move_obj)
            else:
                move_san = move_uci
        except (ValueError, chess.InvalidMoveError):
            move_san = move_uci

        # Parse WDL if available (permille format)
        wdl = None
        if wdl_match:
            w, d, l = map(int, wdl_match.groups())
            wdl = [w, d, l]

        move_data = multipv_data.setdefault(move_san, {})

        # Update with latest data
        if wdl is not None:
            move_data["wdl"] = wdl

    # Parse info string lines for detailed stats (visits, policy, Q-value)
    verbose_data = {}
    
    for line in lines:
        if "info string" not in line:
            continue
        
        match = INFO_STRING_RE.search(line)
        if not match:
            continue
        
        move_uci = match.group(1)
        visits = int(match.group(2))
        policy_pct = float(match.group(3))
        q_value_str = match.group(4)  # Q-value
        
        # Convert UCI to SAN
        try:
            move_obj = chess.Move.from_uci(move_uci)
            if move_obj in board.legal_moves:
                move_san = board.san(move_obj)
            else:
                move_san = move_uci
        except (ValueError, chess.InvalidMoveError):
            move_san = move_uci
        
        verbose_data[move_san] = {
            "visits": visits,
            "policy": round(policy_pct / 100.0, 4),  # Convert percentage to decimal
        }
        
        if q_value_str:
            try:
                verbose_data[move_san]["q_value"] = round(float(q_value_str), 5)
            except ValueError:
                pass
    
    # Combine data from multipv and verbose info
    candidates = []
    for move_san, mpv_data in multipv_data.items():
        candidate = {"move": move_san}
        
        # Add visits from verbose data if available
        if move_san in verbose_data:
            candidate["visits"] = verbose_data[move_san]["visits"]
            if "policy" in verbose_data[move_san]:
                candidate["policy"] = verbose_data[move_san]["policy"]
            if "q_value" in verbose_data[move_san]:
                candidate["q_value"] = verbose_data[move_san]["q_value"]
        
        # Add WDL from multipv data
        if "wdl" in mpv_data:
            candidate["wdl"] = mpv_data["wdl"]
        
        candidates.append(candidate)
    
    # Recalculate ranks based on final VerboseMoveStats data to ensure consistency
    # Sorting criteria matches LC0's GetBestChildrenNoTemperature:
    # 1. Highest visit count
    # 2. If tied, highest Q-value
    # 3. If tied, highest policy
    candidates.sort(key=lambda x: (
        -(x.get("visits", 0)),           # Negative for descending (highest first)
        -(x.get("q_value", -999.0)),     # Negative for descending
        -(x.get("policy", 0.0))          # Negative for descending
    ))
    
    # Assign new ranks based on sorted order and reorder fields
    for rank, candidate in enumerate(candidates, start=1):
        # Rebuild candidate dict with rank right after move
        move = candidate["move"]
        reordered = {"move": move, "rank": rank}
        for key in ["visits", "policy", "q_value", "wdl"]:
            if key in candidate:
                reordered[key] = candidate[key]
        candidates[rank - 1] = reordered
    
    # Limit to max_candidates after re-ranking
    candidates = candidates[:max_candidates]
    
    # Build evaluation for the played move
    evaluation = None
    played_move_data = None
    
    # First, try to find the played move in candidates (has WDL data)
    for candidate in candidates:
        if candidate["move"] == played_move_san:
            played_move_data = candidate
            break
    
    # If not in candidates, check if it's in verbose_data (all legal moves)
    if not played_move_data and played_move_san in verbose_data:
        # Determine rank by counting how many moves in verbose_data have more visits
        played_visits = verbose_data[played_move_san].get("visits", 0)
        rank = 1
        for move_san, data in verbose_data.items():
            if data.get("visits", 0) > played_visits:
                rank += 1
        
        played_move_data = {
            "move": played_move_san,
            "rank": rank,
            "visits": verbose_data[played_move_san].get("visits"),
            "policy": verbose_data[played_move_san].get("policy"),
            "q_value": verbose_data[played_move_san].get("q_value"),
        }
        # Note: WDL not available yet for moves outside MultiPV (will be added later)
        
        # Add the played move to candidates list so it appears in output
        candidates.append(played_move_data)
    
    # Build evaluation from played move data
    total_visits = None
    visits_on_better = None
    
    if played_move_data:
        evaluation = {}
        
        # Order matches candidate_moves: rank, visits, policy, q_value, wdl
        if "rank" in played_move_data:
            evaluation["rank"] = played_move_data["rank"]
        
        if "visits" in played_move_data and played_move_data["visits"] is not None:
            evaluation["visits"] = played_move_data["visits"]
        
        if "policy" in played_move_data and played_move_data["policy"] is not None:
            evaluation["policy"] = played_move_data["policy"]
        
        if "q_value" in played_move_data and played_move_data["q_value"] is not None:
            evaluation["q_value"] = played_move_data["q_value"]
        
        if "wdl" in played_move_data:
            evaluation["wdl"] = played_move_data["wdl"]
    
    # Calculate total visits across all moves from verbose_data
    if verbose_data:
        total_visits = sum(
            move_data.get("visits", 0)
            for move_data in verbose_data.values()
        )
        if total_visits == 0:
            total_visits = None
    
    # Calculate visits on moves ranked strictly better than played move
    # Always 0 when played move is rank 1 (best move)
    if played_move_data and "rank" in played_move_data:
        played_visits = played_move_data.get("visits", 0)
        visits_on_better = sum(
            move_data.get("visits", 0)
            for move_data in verbose_data.values()
            if move_data.get("visits", 0) > played_visits
        )
        # visits_on_better is 0 when rank 1 (no moves are better)
        # This is more principled than having the field disappear
    
    return candidates, evaluation, total_visits, visits_on_better


def _parse_elo(elo_str: Optional[str]) -> Optional[int]:
    """Parse ELO rating from string."""
    if not elo_str:
        return None
    try:
        return int(elo_str)
    except ValueError:
        return None


def _stringify_option(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _resolve_config_paths(config: Dict[str, Any], config_path: pathlib.Path) -> Dict[str, Any]:
    resolved = dict(config)
    base = config_path.parent
    for key in ("lc0_path", "weights"):
        if key in resolved:
            resolved[key] = _resolve_path(base, pathlib.Path(resolved[key]))
    return resolved


def _resolve_path(base: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    if target.is_absolute():
        return target
    return (base / target).resolve()


def _apply_config_override(config: Dict[str, Any], key: str, value: str):
    """Apply a config override from command line.
    
    Supports nested keys with dot notation (e.g., 'search.value').
    Automatically converts value to appropriate type (int, float, bool, str).
    """
    # Split key by dots for nested access
    keys = key.split(".")
    
    # Navigate to the parent dict
    current = config
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
    
    # Convert value to appropriate type
    final_key = keys[-1]
    converted_value: Any
    
    # Try to parse as int
    try:
        converted_value = int(value)
    except ValueError:
        # Try to parse as float
        try:
            converted_value = float(value)
        except ValueError:
            # Try to parse as boolean
            if value.lower() in ("true", "yes", "1"):
                converted_value = True
            elif value.lower() in ("false", "no", "0"):
                converted_value = False
            else:
                # Keep as string
                converted_value = value
    
    current[final_key] = converted_value


def main():
    parser = argparse.ArgumentParser(
        description="Analyze PGN with lc0, writing SAN notation directly (no temp files)",
        epilog="""
Examples:
  # Basic usage with default config
  %(prog)s game.pgn output.json
  
  # Override search to 10 nodes
  %(prog)s game.pgn output.json --search.nodes=10
  
  # Combine search and lc0 options
  %(prog)s game.pgn output.json --search.nodes=50 --lc0.backend=cuda-fp16 --lc0.threads=4
  
  # Alternative: use --lc0-args for multiple lc0 options
  %(prog)s game.pgn output.json --search.nodes=50 --lc0-args backend=cuda-fp16 threads=4
  
  # Use --set for any config override
  %(prog)s game.pgn output.json --set search.value=100 --set max_candidates=3
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pgn", type=pathlib.Path, help="PGN file to analyze")
    parser.add_argument("output", type=pathlib.Path, help="Output JSON file")
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        default=pathlib.Path("config/lc0_config.json"),
        help="Path to JSON config describing lc0 execution parameters",
    )
    parser.add_argument(
        "--lc0-args",
        nargs="*",
        help="lc0 command-line arguments in KEY=VALUE format (e.g., --lc0-args backend=cuda-fp16 threads=4). Overrides config.extra_args.",
        default=None,
    )
    parser.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        help="Override config values (e.g., --set search.value=10 --set max_candidates=3). Can be used multiple times.",
        default=None,
    )
    
    parser.epilog += """
    
Additional options:
  --search.nodes=N      Set UCI search to N nodes (shortcut for --set search.type=nodes --set search.value=N)
  --search.movetime=N   Set UCI search to N milliseconds
  --search.depth=N      Set UCI search to depth N
  --lc0.OPTION=VALUE    Set lc0 option (e.g., --lc0.threads=4, --lc0.backend=cuda-fp16)
"""
    
    # Add support for --search.* and --lc0.* arguments
    args, unknown = parser.parse_known_args()
    
    # Parse --search.* arguments from unknown args
    search_overrides = {}
    lc0_overrides = {}
    remaining_unknown = []
    
    for arg in unknown:
        if arg.startswith("--search."):
            # Handle --search.nodes=10 or --search.nodes 10
            if "=" in arg:
                key, value = arg[2:].split("=", 1)  # Remove -- prefix
                search_overrides[key] = value
            else:
                remaining_unknown.append(arg)
        elif arg.startswith("--lc0."):
            # Handle --lc0.backend=cuda or --lc0.threads=4
            if "=" in arg:
                key, value = arg[6:].split("=", 1)  # Remove --lc0. prefix
                lc0_overrides[key] = value
            else:
                remaining_unknown.append(arg)
        else:
            remaining_unknown.append(arg)
    
    # Report any truly unknown arguments
    if remaining_unknown:
        parser.error(f"Unrecognized arguments: {' '.join(remaining_unknown)}")
    
    if not args.config.exists():
        raise SystemExit(f"Config file not found: {args.config}")

    with args.config.open(encoding="utf-8") as cfg_file:
        raw_config = json.load(cfg_file)

    resolved_config = _resolve_config_paths(raw_config, args.config)

    # Process --lc0-args (KEY=VALUE format)
    # These become lc0 command-line arguments like --key=value
    extra_args = []
    if args.lc0_args is not None:
        for arg in args.lc0_args:
            if "=" in arg:
                key, value = arg.split("=", 1)
                extra_args.append(f"--{key}={value}")
            else:
                # If no =, treat as a flag
                extra_args.append(f"--{arg}")
        resolved_config["extra_args"] = extra_args
    
    # Process --lc0.* arguments (alternative syntax)
    if lc0_overrides:
        if "extra_args" not in resolved_config:
            resolved_config["extra_args"] = []
        for key, value in lc0_overrides.items():
            resolved_config["extra_args"].append(f"--{key}={value}")
    
    # Apply config overrides from --set arguments
    if args.set:
        for override in args.set:
            if "=" not in override:
                raise SystemExit(f"Invalid --set format: '{override}'. Expected KEY=VALUE")
            key, value = override.split("=", 1)
            _apply_config_override(resolved_config, key, value)
    
    # Apply --search.* arguments to override search config
    if search_overrides:
        if "search" not in resolved_config:
            resolved_config["search"] = {}
        for key, value in search_overrides.items():
            # Extract search type from key (handles "search.nodes" or just "nodes")
            search_type = key.split(".", 1)[-1]  # Get last part after split
            
            if search_type == "infinite":
                resolved_config["search"]["type"] = "infinite"
                resolved_config["search"]["value"] = 0
            else:
                resolved_config["search"]["type"] = search_type
                resolved_config["search"]["value"] = int(value)

    required_keys = {"lc0_path", "weights"}
    missing = [key for key in required_keys if key not in resolved_config]
    if missing:
        raise SystemExit(f"Missing required config keys: {', '.join(missing)}")

    analyze_pgn(resolved_config, args.pgn, args.output)


if __name__ == "__main__":
    main()
