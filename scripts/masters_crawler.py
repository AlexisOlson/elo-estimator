"""
Lichess Masters Opening Explorer Crawler

Finds top-N expert human opening lines using best-first search,
tracking W/D/L counts per time bucket (yearly).

Algorithm:
- Best-first search: expand nodes with highest information score
- Depth-dependent pruning: min_count(depth) = max(M0 * decay^depth, Mmin)
- Transposition deduplication by FEN
- UCI move computation via python-chess

Output: CSV with columns matching the spec
"""

import csv
import time
import math
import heapq
import requests
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import chess


# ============================================================================
# Configuration
# ============================================================================

MASTERS_URL = "https://explorer.lichess.ovh/masters"
HEADERS = {"User-Agent": "opening-explorer/2.0 (research)"}
RATE_LIMIT_SLEEP = 0.12  # seconds between API calls


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class MoveStats:
    """W/D/L statistics for a move"""
    uci: str
    san: str
    white: int
    draws: int
    black: int

    @property
    def total(self) -> int:
        return self.white + self.draws + self.black


@dataclass
class Line:
    """A complete opening line with metadata"""
    san_moves: List[str]
    final_fen: str
    depth: int
    white: int
    draws: int
    black: int
    min_node_count: int
    score_sumlog: float  # sum of log(count) along the path

    @property
    def total(self) -> int:
        return self.white + self.draws + self.black

    @property
    def san_line(self) -> str:
        return " ".join(self.san_moves)


@dataclass(order=True)
class SearchNode:
    """Priority queue node for best-first search"""
    priority: float = field(compare=True)  # negative for max-heap
    fen: str = field(compare=False)
    san_moves: List[str] = field(compare=False)
    depth: int = field(compare=False)
    score_sumlog: float = field(compare=False)
    min_node_count: int = field(compare=False)


# ============================================================================
# Position Cache & API
# ============================================================================

class PositionCache:
    """Fetches positions from Lichess Masters API with caching"""

    def __init__(self, since: int, until: int, rate_limit: float = RATE_LIMIT_SLEEP):
        self.since = since
        self.until = until
        self.rate_limit = rate_limit
        self.cache: Dict[str, Dict] = {}
        self.api_calls = 0
        self.last_call_time = 0.0

    def fetch(self, fen: str, moves: int = 40) -> Dict:
        """Fetch position data from API or cache"""
        if fen in self.cache:
            return self.cache[fen]

        # Rate limiting
        elapsed = time.time() - self.last_call_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

        # API call
        params = {
            "fen": fen,
            "since": self.since,
            "until": self.until,
            "moves": moves
        }

        try:
            response = requests.get(
                MASTERS_URL,
                params=params,
                headers=HEADERS,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            self.last_call_time = time.time()
            self.api_calls += 1
            self.cache[fen] = data

            return data

        except requests.RequestException as e:
            print(f"API error for FEN {fen[:30]}...: {e}")
            return {"white": 0, "draws": 0, "black": 0, "moves": []}

    def get_children(self, fen: str) -> List[MoveStats]:
        """Get all legal moves with statistics from this position"""
        data = self.fetch(fen)
        moves = []

        for mv in data.get("moves", []):
            moves.append(MoveStats(
                uci=mv["uci"],
                san=mv["san"],
                white=mv["white"],
                draws=mv["draws"],
                black=mv["black"]
            ))

        return moves

    def apply_move(self, fen: str, uci: str) -> Optional[str]:
        """Apply UCI move to FEN and return new FEN"""
        try:
            board = chess.Board(fen)
            move = chess.Move.from_uci(uci)
            board.push(move)
            return board.fen()
        except (ValueError, chess.IllegalMoveError):
            return None


# ============================================================================
# Line Explorer
# ============================================================================

class LineExplorer:
    """Best-first search to find top opening lines"""

    def __init__(
        self,
        cache: PositionCache,
        min_games: int = 100,
        max_depth: Optional[int] = None,
        line_callback = None
    ):
        self.cache = cache
        self.min_games = min_games
        self.max_depth = max_depth  # None = unlimited
        self.line_callback = line_callback  # Called for each discovered line

        # Search state
        self.visited_fens = set()
        self.all_lines: List[Line] = []

    def depth_threshold(self, depth: int) -> int:
        """Minimum count required at this depth (constant threshold)"""
        return self.min_games

    def info_score(self, count: int, parent_total: int) -> float:
        """Information score: count * (-log(count/parent_total))"""
        if parent_total == 0 or count == 0:
            return 0.0
        prob = count / parent_total
        return count * (-math.log(prob))

    def explore(self, max_nodes: Optional[int] = None) -> List[Line]:
        """
        Explore opening tree using best-first search.

        Args:
            max_nodes: Maximum nodes to explore (None = exhaustive until frontier empty)

        Returns all discovered lines (not filtered to top-N yet).
        """
        start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

        # Priority queue: (negative_priority, node)
        # Use negative priority for max-heap behavior
        frontier = []
        heapq.heappush(frontier, SearchNode(
            priority=0.0,
            fen=start_fen,
            san_moves=[],
            depth=0,
            score_sumlog=0.0,
            min_node_count=float('inf')
        ))

        self.visited_fens.add(start_fen)
        nodes_explored = 0

        while frontier:
            # Check node budget if specified
            if max_nodes is not None and nodes_explored >= max_nodes:
                break

            node = heapq.heappop(frontier)
            nodes_explored += 1

            # Don't expand beyond max depth (if specified)
            if self.max_depth is not None and node.depth >= self.max_depth:
                continue

            # Get parent statistics
            parent_data = self.cache.fetch(node.fen)
            parent_total = parent_data["white"] + parent_data["draws"] + parent_data["black"]

            if parent_total == 0:
                continue

            # Get children and apply depth threshold
            children = self.cache.get_children(node.fen)
            threshold = self.depth_threshold(node.depth)

            # Score and sort children by information score
            scored_children = []
            for child in children:
                if child.total >= threshold:
                    score = self.info_score(child.total, parent_total)
                    scored_children.append((score, child))

            scored_children.sort(reverse=True, key=lambda x: x[0])

            # Process each child
            for _, child in scored_children:
                # Compute child FEN
                child_fen = self.cache.apply_move(node.fen, child.uci)
                if child_fen is None:
                    continue

                # Skip if already visited (transposition)
                if child_fen in self.visited_fens:
                    continue

                self.visited_fens.add(child_fen)

                # Build new path
                new_san_moves = node.san_moves + [child.san]
                new_depth = node.depth + 1
                new_min_count = min(node.min_node_count, child.total)
                new_score_sumlog = node.score_sumlog + math.log(child.total + 1)

                # Record this line
                line = Line(
                    san_moves=new_san_moves,
                    final_fen=child_fen,
                    depth=new_depth,
                    white=child.white,
                    draws=child.draws,
                    black=child.black,
                    min_node_count=new_min_count,
                    score_sumlog=new_score_sumlog
                )
                self.all_lines.append(line)

                # Call callback if provided (for incremental CSV writing)
                if self.line_callback:
                    self.line_callback(line)

                # Add to frontier for further exploration
                # Priority: combination of score and depth
                priority = -(new_score_sumlog + new_depth * 0.5)

                heapq.heappush(frontier, SearchNode(
                    priority=priority,
                    fen=child_fen,
                    san_moves=new_san_moves,
                    depth=new_depth,
                    score_sumlog=new_score_sumlog,
                    min_node_count=new_min_count
                ))

        print(f"  Explored {nodes_explored} nodes, found {len(self.all_lines)} lines")
        print(f"  API calls: {self.cache.api_calls}")

        return self.all_lines


# ============================================================================
# Main Crawling Logic
# ============================================================================

def crawl_masters_by_year(
    years: List[Tuple[int, int]],
    output_file: str,
    N: Optional[int] = None,
    min_games: int = 100,
    max_depth: Optional[int] = None,
    max_nodes_per_bucket: Optional[int] = None
):
    """
    Crawl Masters database for multiple time buckets.
    Writes lines to CSV incrementally as they are discovered.

    Args:
        years: List of (since, until) year pairs
        output_file: Path to output CSV file
        N: Number of top lines to extract per bucket (None = all lines)
        min_games: Constant minimum game threshold for all depths
        max_depth: Maximum ply depth (None = unlimited)
        max_nodes_per_bucket: Budget for nodes explored per time bucket (None = exhaustive)
    """
    fieldnames = [
        "source", "period", "speed", "rating_bucket", "depth",
        "san_line", "final_fen", "white", "draws", "black", "total",
        "min_node_count", "score_sumlog"
    ]

    # Open CSV file and write header
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        csvfile.flush()

        total_lines_written = 0

        for since, until in years:
            print(f"\n{'='*60}")
            print(f"Processing: {since}-{until}")
            print(f"{'='*60}")

            # Create callback to write each line immediately
            def write_line_to_csv(line: Line):
                nonlocal total_lines_written
                row = {
                    "source": "masters",
                    "period": f"{since}-{until}",
                    "speed": "",
                    "rating_bucket": "",
                    "depth": line.depth,
                    "san_line": line.san_line,
                    "final_fen": line.final_fen,
                    "white": line.white,
                    "draws": line.draws,
                    "black": line.black,
                    "total": line.total,
                    "min_node_count": line.min_node_count,
                    "score_sumlog": round(line.score_sumlog, 4)
                }
                writer.writerow(row)
                csvfile.flush()  # Ensure data is written to disk
                total_lines_written += 1

                # Progress indicator every 50 lines
                if total_lines_written % 50 == 0:
                    print(f"  ... {total_lines_written} lines written so far")

            # Create cache and explorer for this time bucket
            cache = PositionCache(since=since, until=until)
            explorer = LineExplorer(
                cache=cache,
                min_games=min_games,
                max_depth=max_depth,
                line_callback=write_line_to_csv
            )

            # Explore the tree (lines written as discovered)
            lines = explorer.explore(max_nodes=max_nodes_per_bucket)

            print(f"  Found {len(lines)} lines for this period")

        print(f"\n{'='*60}")
        print(f"Total: {total_lines_written} lines written to {output_file}")
        print(f"{'='*60}")


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    # Configuration - Single global year bucket
    # Lichess Masters database contains OTB games from ~1952 onwards
    YEAR_BUCKETS = [
        (1952, 2024),  # All years in one bucket
    ]

    OUTPUT_FILE = "output/masters_lines_200games.csv"

    # Run crawler
    print("Masters Opening Line Crawler - GLOBAL DATASET")
    print("="*60)
    print("Mode: EXHAUSTIVE - Finding all positions with >=200 games")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Year range: 1952-2024 (single global bucket)")
    print("No depth limit - will explore until frontier exhausted")
    print("Lines will be written incrementally as discovered")
    print()

    crawl_masters_by_year(
        years=YEAR_BUCKETS,
        output_file=OUTPUT_FILE,
        N=None,              # Keep all lines (no filtering)
        min_games=200,       # 200 games minimum
        max_depth=None,      # No depth limit
        max_nodes_per_bucket=None  # Exhaustive search until frontier empty
    )

    print("\nDone!")
