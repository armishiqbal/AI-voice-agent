"""Compare deterministic chunk sizes before Pinecone ingestion."""

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.services.ingestion import compare_chunk_sizes

    print(json.dumps(compare_chunk_sizes(args.path.read_text(encoding="utf-8"), args.source), indent=2))
