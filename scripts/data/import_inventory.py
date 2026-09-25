"""Validate and import a CSV/JSON inventory file."""

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--source", required=True, help="Authoritative inventory source/version label")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.repositories.bootstrap import create_schema_for_local_development
    from app.repositories.properties import SqlPropertyRepository
    from app.services.ingestion import parse_inventory_bytes

    create_schema_for_local_development()
    result = parse_inventory_bytes(args.path.read_bytes(), args.path.name, args.source)
    batch_id = SqlPropertyRepository().import_properties(
        result.records,
        source=result.source,
        validation_errors=[issue.as_dict() for issue in result.errors],
    )
    print(json.dumps({"batch_id": batch_id, "source": result.source, "imported": len(result.records), "errors": [issue.as_dict() for issue in result.errors]}, indent=2))
