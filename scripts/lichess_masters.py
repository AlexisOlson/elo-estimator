import csv, time, math, requests
from collections import deque
import chess

MASTERS_URL = "https://explorer.lichess.ovh/masters"
HEADERS = {"User-Agent": "opening-sampler/1.0 (research)"}

def fetch_counts(fen, since, until, moves=20, sleep=0.2, max_retries=5):
    """Return dict: {'white': int, 'draws': int, 'black': int, 'moves': [{'uci','san','white','draws','black'}]}"""
    params = {"fen": fen, "since": since, "until": until, "moves": moves}

    for attempt in range(max_retries):
        try:
            r = requests.get(MASTERS_URL, params=params, headers=HEADERS, timeout=15)
            r.raise_for_status()
            time.sleep(sleep)  # be polite
            return r.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limited - wait with exponential backoff
                wait_time = sleep * (2 ** attempt) * 10  # 2s, 4s, 8s, 16s, 32s
                print(f"  Rate limited! Waiting {wait_time:.1f}s before retry {attempt+1}/{max_retries}...")
                time.sleep(wait_time)
                if attempt == max_retries - 1:
                    raise  # Give up after max retries
            else:
                raise  # Re-raise other HTTP errors
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = sleep * (2 ** attempt)
            print(f"  Error: {e}. Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)

    raise Exception(f"Failed after {max_retries} retries")

def children_sorted_by_info(parent, child_list):
    total = parent["white"] + parent["draws"] + parent["black"]
    scored = []
    for i, mv in enumerate(child_list):
        c = mv["white"] + mv["draws"] + mv["black"]
        if c <= 0: continue
        p = c / total
        info = c * (-math.log(p))  # popular & discriminating
        scored.append((info, c, i, mv))  # Add index to break ties
    scored.sort(reverse=True)
    return [mv for _,_,_,mv in scored]

def top_lines(since, until, N=1000, M0=500, decay=0.6, Mmin=40, max_depth=20, line_callback=None):
    """
    Fetch top lines from Masters database.

    line_callback: Optional function called with each line as it's collected: callback(line_dict)
    """
    start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    root = fetch_counts(start_fen, since, until, moves=40)
    # BFS on (fen, san_line, depth, score_aggr, min_count)
    # We'll expand nodes ordered by an aggregate that rewards depth but protects against tiny tails.
    frontier = deque([(start_fen, [], 0, 0.0, float('inf'))])
    lines = []

    seen = set([start_fen])  # simple transposition guard per search
    positions_fetched = 0
    while frontier and len(lines) < N:
        fen, san_path, depth, score_aggr, min_cnt = frontier.popleft()
        parent = fetch_counts(fen, since, until, moves=40)
        positions_fetched += 1
        if positions_fetched % 50 == 0:
            print(f"  Fetched {positions_fetched} positions, collected {len(lines)}/{N} lines...")
        total_parent = parent["white"] + parent["draws"] + parent["black"]
        if depth >= max_depth or total_parent == 0:
            continue

        # threshold by depth
        thresh = max(int(M0 * (decay ** depth)), Mmin)
        kids = [mv for mv in children_sorted_by_info(parent, parent["moves"])
                if (mv["white"]+mv["draws"]+mv["black"]) >= thresh]

        for mv in kids:
            c = mv["white"]+mv["draws"]+mv["black"]
            # Get child FEN - compute if not provided by API
            child_fen = mv.get("fen")
            if not child_fen:
                # Compute FEN using python-chess
                try:
                    board = chess.Board(fen)
                    uci_move = mv.get("uci")
                    if uci_move:
                        board.push_uci(uci_move)
                        child_fen = board.fen()
                    else:
                        continue  # Skip if no UCI move available
                except:
                    continue  # Skip if move is invalid

            if (child_fen, depth+1) in seen:  # cheap transposition guard by depth
                continue
            seen.add((child_fen, depth+1))

            new_path = san_path + [mv["san"]]
            new_min = min(min_cnt, c)
            new_score = score_aggr + math.log(c+1)

            # line record at each step (so you get all prefixes)
            line_dict = {
                "since": since, "until": until,
                "depth": depth+1,
                "san_line": " ".join(new_path),
                "fen": child_fen,
                "white": mv["white"], "draws": mv["draws"], "black": mv["black"],
                "total": c,
                "count": c, "min_node_count": new_min, "score_sumlog": new_score
            }
            lines.append(line_dict)

            # Call callback if provided (for streaming writes)
            if line_callback:
                line_callback(line_dict)

            if len(lines) >= N:
                break

            # continue expanding
            frontier.append((child_fen, new_path, depth+1, new_score, new_min))

    # take the best N by a robust criterion (geomean-ish)
    lines.sort(key=lambda r: (r["min_node_count"], r["score_sumlog"]), reverse=True)
    return lines[:N]

if __name__ == "__main__":
    rows = top_lines(since=2018, until=2024, N=1000, M0=600, decay=0.65, Mmin=50, max_depth=20)
    with open("masters_top1000_2018_2024.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("Wrote masters_top1000_2018_2024.csv")
