"""Validate and import a CSV/JSON inventory file."""

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--source", required=True, help="Authoritative inventory source/version label")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the inventory without creating a schema, batch, or listing",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.services.ingestion import parse_inventory_bytes

    result = parse_inventory_bytes(args.path.read_bytes(), args.path.name, args.source)
    preview = {
        "source": result.source,
        "accepted": len(result.records),
        "rejected": len(result.errors),
        "validation_errors": [issue.as_dict() for issue in result.errors],
    }
    if args.dry_run or result.errors or not result.records:
        print(json.dumps(preview, indent=2))
        if args.dry_run and not result.errors and result.records:
            sys.exit(0)
        sys.exit(2)

    from app.repositories.bootstrap import create_schema_for_local_development
    from app.repositories.properties import SqlPropertyRepository

    create_schema_for_local_development()
    batch_id = SqlPropertyRepository().import_properties(
        result.records,
        source=result.source,
    )
    print(json.dumps({**preview, "batch_id": batch_id, "imported": len(result.records)}, indent=2))
