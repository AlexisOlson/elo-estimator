#!/usr/bin/env python3
"""Reformat JSON output files to match current candidate move format.

Reads JSON, reformats with proper alignment and spacing to match single_test_100nodes.json:
- Move names: right-padded to 4 characters with spaces
- Rank: right-aligned with spaces (no zero-padding)
- Visits: right-aligned with spaces (no zero-padding)
- Policy: 4 decimal places
- Q-value: 5 decimal places with aligned decimal points
- Field order: move, rank, visits, policy, q_value, wdl
"""

import json
import sys
from pathlib import Path


def reformat_json_file(input_path, output_path=None):
    """Reformat a JSON file with proper candidate move formatting."""
    if output_path is None:
        output_path = input_path
    
    print(f"Reading {input_path}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Count moves for progress
    total_moves = 0
    for game in data.get("games", []):
        for move_info in game.get("moves", []):
            total_moves += len(move_info.get("candidate_moves", []))
    
    print(f"Reformatting {total_moves} candidate moves...")
    
    # Write with custom formatting
    print(f"Writing {output_path}...")
    write_formatted_json(data, output_path)
    print("Done!")


def write_formatted_json(data, output_path):
    """Write JSON with compact formatting matching analyze_pgn.py logic."""
    import re
    
    # First pass: standard JSON with indentation
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    
    # Compact WDL arrays
    json_str = re.sub(
        r'\[\s+(\d+),\s+(\d+),\s+(\d+)\s+\]',
        r'[\1, \2, \3]',
        json_str
    )
    
    # Compact evaluation objects to single line
    eval_pattern = r'(\s*)"evaluation":\s*\{\s*([^}]+?)\s*\}'
    def compact_eval(match):
        leading_indent = match.group(1)
        fields = match.group(2)
        # Remove newlines and compress multiple spaces to single space
        fields_compact = re.sub(r'\s+', ' ', fields).strip()
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
                    # Pad the move string itself (spaces after the closing quote)
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
    
    json_str = '\n'.join(result_lines)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(json_str)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reformat_json.py <input_file> [output_file]")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else input_file
    
    reformat_json_file(input_file, output_file)
