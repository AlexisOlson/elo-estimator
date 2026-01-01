## What's New

This release adds position complexity metrics to the JSON output via the new `total_legal_moves` field.

### New Features

- **`total_legal_moves` field**: Reports the total number of legal moves available for each position
  - Provides a measure of position complexity (branching factor)
  - Useful for ML model training to understand move space size
  - Field appears before `total_visits` in the output structure

### Example Output

```json
{
  "ply": 1,
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "to_move": "white",
  "total_legal_moves": 20,
  "total_visits": 1022,
  "visits_on_better": 654,
  "played_move": "e4",
  "evaluation": {...},
  "candidate_moves": [...]
}
```

### Documentation Updates

- Updated README.md with new field examples
- Updated docs/output_format.json with field specification
- Updated CHANGELOG.md with release notes

### Testing

Verified with sample analysis showing correct values:
- Starting position: 20 legal moves ✓
- After 1.e4: 20 legal moves ✓
- After 1...e5: 29 legal moves ✓

### What's Changed

**Full Changelog**: https://github.com/AlexisOlson/elo-estimator/compare/v1.2.0...v1.3.0

---

This release builds on v1.2.0's ClearTree integration for consistent position-independent evaluations.

🤖 Generated with [Claude Code](https://claude.com/claude-code)