#!/usr/bin/env python3
"""Extract selected positions from an analyzer JSON using a CSV of target positions.

Reads `output/PosA_thru_PosH.json` and `EvaluatingEightPositions_TopTable.csv` (root).
Writes a compact JSON file `output/PosA_positions_extracted.json` containing one
object per Pos (PosA..PosH) with metadata and the ply-1 move record.
"""
import csv
import json
import pathlib
import re
from typing import Any, Dict
import importlib.util

def _get_compact_dumper(root: pathlib.Path):
    """Load analyzer's _compact_json_dumps from scripts/analyze_pgn.py dynamically."""
    analyzer_path = root / 'scripts' / 'analyze_pgn.py'
    spec = importlib.util.spec_from_file_location('analyze_pgn', str(analyzer_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return getattr(mod, '_compact_json_dumps')


def load_csv(csv_path: pathlib.Path) -> Dict[str, Dict[str, str]]:
    mapping = {}
    with csv_path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pos = row.get('Pos')
            if not pos:
                continue
            mapping[pos] = {
                'MostCommonMoveOrder': row.get('Most Common Move Order', ''),
                'OpeningLine': row.get('Opening Line', ''),
                'WhiteAvgScore': row.get('White Avg Score (human games)', ''),
            }
    return mapping


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    json_in = root / 'output' / 'PosA_thru_PosH.json'
    csv_in = root / 'EvaluatingEightPositions_TopTable.csv'
    out_path = root / 'output' / 'PosA_positions_extracted.json'

    if not json_in.exists():
        raise SystemExit(f"Input JSON not found: {json_in}")
    if not csv_in.exists():
        raise SystemExit(f"CSV file not found: {csv_in}")

    pos_meta = load_csv(csv_in)

    data = json.loads(json_in.read_text(encoding='utf-8'))
    games = data.get('games', [])

    # prepare sequence extractor
    def parse_sequence(seq: str):
        # split on whitespace and strip leading move numbers like '12.'
        tokens = []
        for tok in seq.split():
            # remove leading digits and dots (e.g., '12.0-0-0' -> '0-0-0')
            t = re.sub(r'^\d+\.', '', tok)
            if t:
                tokens.append(t)
        return tokens

    def find_sequence_index(moves_list, seq_tokens):
        # moves_list: list of SAN strings; seq_tokens: list of SAN tokens to match in order
        if not seq_tokens:
            return None
        n = len(moves_list)
        m = len(seq_tokens)
        for start in range(0, n - m + 1):
            ok = True
            for i in range(m):
                if moves_list[start + i] != seq_tokens[i]:
                    ok = False
                    break
            if ok:
                return start + m - 1  # index of last matched token
        # fallback: try to match the tail of the sequence (last up to 6 moves)
        for tail in range(min(m, 6), 0, -1):
            tail_tokens = seq_tokens[-tail:]
            for start in range(0, n - tail + 1):
                ok = True
                for i in range(tail):
                    if moves_list[start + i] != tail_tokens[i]:
                        ok = False
                        break
                if ok:
                    return start + tail - 1
        return None

    extracted = []
    # for formatting reuse analyzer dumper if available
    compact_dumper = _get_compact_dumper(root)

    for game in games:
        site = game.get('site')
        if site not in pos_meta:
            continue
        seq = pos_meta[site].get('MostCommonMoveOrder')
        if not seq:
            continue

        # build played_move SAN list
        moves = game.get('moves', [])
        san_list = [m.get('played_move') for m in moves if isinstance(m, dict) and 'played_move' in m]

        seq_tokens = parse_sequence(seq)
        idx = find_sequence_index(san_list, seq_tokens)
        if idx is None:
            # couldn't find match; skip
            continue
        target_idx = idx + 1
        if target_idx >= len(moves):
            continue

        selected = moves[target_idx]

        extracted.append({
            'pos': site,
            'game_index': game.get('game_index'),
            'white': game.get('white'),
            'black': game.get('black'),
            'event': game.get('event'),
            'selected_move': selected,
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Use compact dumper to match analyzer style when available
    content = {'positions': extracted}
    try:
        dump = compact_dumper(content, indent=2)
    except Exception:
        dump = json.dumps(content, indent=2)
    out_path.write_text(dump, encoding='utf-8')
    print(f"Wrote {out_path} with {len(extracted)} positions")


if __name__ == '__main__':
    main()
