"""Extract brochure/FAQ chunks and upsert them into configured Pinecone."""

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--property-id")
    parser.add_argument("--city")
    parser.add_argument("--language", default="en")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "backend"))
    from app.core.config import settings
    from app.integrations.rag import build_knowledge_store
    from app.services.ingestion import chunk_text, extract_pdf_chunks

    store = build_knowledge_store(settings)
    if store is None:
        raise SystemExit("Configure OPENAI_API_KEY, PINECONE_API_KEY, and PINECONE_INDEX first")
    metadata = {key: value for key, value in {"property_id": args.property_id, "city": args.city, "language": args.language}.items() if value}
    if args.path.suffix.lower() == ".pdf":
        chunks = extract_pdf_chunks(args.path.read_bytes(), args.path.name, args.source, metadata=metadata)
    else:
        chunks = chunk_text(args.path.read_text(encoding="utf-8"), args.source, metadata=metadata)
    store.upsert(chunks)
    print(json.dumps({"source": args.source, "upserted": len(chunks), "namespace": settings.pinecone_namespace}, indent=2))
