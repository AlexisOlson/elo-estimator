#!/usr/bin/env python3
"""Analyze PGN positions with lc0, writing SAN notation directly (no temp files).

This script:
1. Loads lc0 execution parameters from a JSON config file
2. Reads positions from a PGN file
3. Sends each position to lc0 via UCI
4. Parses lc0 output and converts UCI to SAN
5. Writes JSON records directly to output

Zero intermediate files!
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


# Custom JSON encoder for compact WDL arrays
class CompactJSONEncoder(json.JSONEncoder):
    """JSON encoder that formats WDL arrays on single lines."""
    
    def encode(self, obj):
        if isinstance(obj, list) and len(obj) == 3 and all(isinstance(x, int) for x in obj):
            # Compact format for WDL arrays
            return f"[{obj[0]}, {obj[1]}, {obj[2]}]"
        return super().encode(obj)
    
    def iterencode(self, obj, _one_shot=False):
        """Encode while keeping WDL arrays compact."""
        for chunk in super().iterencode(obj, _one_shot):
            yield chunk


def _compact_json_dumps(obj: Any, indent: int = 2) -> str:
    """Serialize obj to JSON with compact WDL arrays."""
    # Use standard json.dumps but post-process to compact WDL arrays
    json_str = json.dumps(obj, indent=indent)
    
    # Replace multi-line WDL arrays with single-line format
    # Pattern: [\n      123,\n      456,\n      789\n    ]
    import re
    pattern = r'\[\s*(\d+),\s*(\d+),\s*(\d+)\s*\]'
    json_str = re.sub(pattern, r'[\1, \2, \3]', json_str)
    
    return json_str


# Regex patterns from parse_lc0_output.py
MULTIPV_RE = re.compile(r"multipv (\d+)")
WDL_RE = re.compile(r"wdl (\d+) (\d+) (\d+)")
PV_RE = re.compile(r" pv (.+)$")
SCORE_CP_RE = re.compile(r"score cp (-?\d+)")
SCORE_MATE_RE = re.compile(r"score mate (-?\d+)")
NODES_RE = re.compile(r"\bnodes (\d+)")

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
    backend = config.get("backend", "cuda-auto")
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
        f"--backend={backend}",
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
        
        print(f"Analyzing game {game_idx + 1}...")
        
        for move in game.mainline_moves():
            fen = board.fen()
            to_move = "white" if board.turn == chess.WHITE else "black"
            played_move_san = board.san(move)
            
            # Send position to lc0
            send_command(f"position fen {fen}")
            send_command(f"go {search_type} {search_value}")
            
            # Read analysis output
            lines = read_until("bestmove")
            
            # Parse candidate moves and evaluation
            candidates, evaluation = parse_analysis(lines, board, max_candidates)
            
            # Build move record
            move_record = {
                "ply": ply,
                "fen": fen,
                "to_move": to_move,
                "played_move": played_move_san,
            }
            
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
    
    # Write complete JSON structure with compact WDL arrays
    with output_path.open("w", encoding="utf-8") as out_file:
        json_str = _compact_json_dumps({"games": all_games}, indent=2)
        out_file.write(json_str)
        out_file.write("\n")
    
    # Cleanup
    send_command("quit")
    process.wait()
    
    print(f"\nDone! Output written to {output_path}")


def parse_analysis(lines: List[str], board: chess.Board, max_candidates: int) -> Tuple[List[Dict], Optional[Dict]]:
    """Parse lc0 output into candidate moves and evaluation.
    
    Returns:
        (candidates, evaluation) where:
        - candidates: List of candidate move dicts with rank, visits, wdl, policy, q_value
        - evaluation: Dict with overall position evaluation (visits, wdl)
    """
    # Parse multipv lines for basic move info and WDL
    multipv_data = {}
    total_nodes = None
    
    for line in lines:
        # Get total nodes from any info line
        if "nodes" in line and "multipv" not in line:
            nodes_match = NODES_RE.search(line)
            if nodes_match and total_nodes is None:
                total_nodes = int(nodes_match.group(1))
        
        if "multipv" not in line:
            continue

        multipv_match = MULTIPV_RE.search(line)
        pv_match = PV_RE.search(line)
        wdl_match = WDL_RE.search(line)
        nodes_match = NODES_RE.search(line)

        # Need at least multipv and pv
        if not (multipv_match and pv_match):
            continue

        pv_moves = pv_match.group(1).split()
        if not pv_moves:
            continue

        move_uci = pv_moves[0]
        multipv_rank = int(multipv_match.group(1))

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

        # Track data for this move
        if move_san not in multipv_data:
            multipv_data[move_san] = {"rank": multipv_rank}
        
        # Update with latest data
        if wdl is not None:
            multipv_data[move_san]["wdl"] = wdl
        if nodes_match:
            # This is per-move nodes in the search line context
            pass  # We'll get better visit counts from info string

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
        candidate = {
            "move": move_san,
            "rank": mpv_data["rank"],
        }
        
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
    
    # Sort by rank and limit to max_candidates
    candidates.sort(key=lambda x: x["rank"])
    candidates = candidates[:max_candidates]
    
    # Build overall evaluation (from rank 1 move or total)
    evaluation = None
    if candidates:
        # Use the top move's data for evaluation
        top_move = candidates[0]
        evaluation = {}
        
        if "visits" in top_move:
            evaluation["visits"] = top_move["visits"]
        elif total_nodes:
            evaluation["visits"] = total_nodes
        
        if "wdl" in top_move:
            evaluation["wdl"] = top_move["wdl"]
        
        if "policy" in top_move:
            evaluation["policy"] = top_move["policy"]
        
        if "q_value" in top_move:
            evaluation["q_value"] = top_move["q_value"]
    
    return candidates, evaluation


def parse_candidates(lines: List[str], board: chess.Board, max_candidates: int) -> List[Dict]:
    """Parse multipv lines into candidate moves with SAN notation.
    
    DEPRECATED: Use parse_analysis instead for full data extraction.
    """
    candidates, _ = parse_analysis(lines, board, max_candidates)
    return candidates


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
