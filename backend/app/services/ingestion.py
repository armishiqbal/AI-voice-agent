from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.domain.models import Property
from app.integrations.rag.pinecone import RetrievedChunk


@dataclass(frozen=True)
class ImportIssue:
    row: int
    field: str
    message: str

    def as_dict(self) -> dict[str, object]:
        return {"row": self.row, "field": self.field, "message": self.message}


@dataclass(frozen=True)
class InventoryImportResult:
    source: str
    records: list[Property]
    errors: list[ImportIssue]


def _coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    values = dict(row)
    for key in ("price_pkr", "bedrooms", "size_sqft"):
        if values.get(key) not in (None, ""):
            try:
                values[key] = int(str(values[key]).replace(",", "").strip())
            except ValueError:
                # Preserve the original value so Pydantic reports the exact field.
                pass
    for key in ("amenities", "investment_goals", "nearby_schools", "nearby_hospitals"):
        if isinstance(values.get(key), str):
            values[key] = [
                item.strip() for item in values[key].replace(",", "|").split("|") if item.strip()
            ]
    if isinstance(values.get("available"), str):
        values["available"] = values["available"].strip().lower() in {"1", "true", "yes", "y"}
    return values


def _validate_rows(rows: list[dict[str, Any]], source: str) -> InventoryImportResult:
    records: list[Property] = []
    errors: list[ImportIssue] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            records.append(Property.model_validate(_coerce_row(row)))
        except (ValidationError, ValueError, TypeError) as error:
            if isinstance(error, ValidationError):
                for issue in error.errors():
                    errors.append(
                        ImportIssue(
                            row_number, ".".join(str(item) for item in issue["loc"]), issue["msg"]
                        )
                    )
            else:
                errors.append(ImportIssue(row_number, "row", str(error)))
    return InventoryImportResult(source=source, records=records, errors=errors)


def parse_inventory_bytes(data: bytes, filename: str, source: str) -> InventoryImportResult:
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        payload = json.loads(data.decode("utf-8"))
        rows = payload.get("properties", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise TypeError("JSON inventory must be a list or an object with a properties list")
        return _validate_rows(rows, source)
    if suffix == ".csv":
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        return _validate_rows([dict(row) for row in reader], source)
    raise ValueError("Inventory files must be .json or .csv")


def chunk_text(
    text: str,
    source: str,
    chunk_size: int = 800,
    overlap: int = 120,
    metadata: dict[str, object] | None = None,
) -> list[RetrievedChunk]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    cleaned = " ".join(text.split())
    chunks: list[RetrievedChunk] = []
    start = 0
    index = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(
            RetrievedChunk(
                source_id=f"{source}#chunk-{index}",
                text=cleaned[start:end],
                score=0.0,
                metadata={
                    "source": source,
                    "version": "import-1",
                    "chunk_index": index,
                    **(metadata or {}),
                },
            )
        )
        if end == len(cleaned):
            break
        start = end - overlap
        index += 1
    return chunks


def extract_pdf_chunks(
    data: bytes,
    filename: str,
    source: str,
    metadata: dict[str, object] | None = None,
) -> list[RetrievedChunk]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError(
            "Install the ingestion extra to process PDF brochures and FAQs"
        ) from error
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return chunk_text(text, source, metadata=metadata)


def compare_chunk_sizes(
    text: str, source: str, sizes: tuple[int, ...] = (400, 800, 1_200)
) -> list[dict[str, float | int]]:
    """Produce reproducible chunk-count/length evidence before choosing an index size."""

    rows: list[dict[str, float | int]] = []
    for size in sizes:
        chunks = chunk_text(text, source, chunk_size=size, overlap=max(20, size // 8))
        rows.append(
            {
                "chunk_size": size,
                "chunk_count": len(chunks),
                "average_characters": round(
                    sum(len(chunk.text) for chunk in chunks) / len(chunks), 2
                )
                if chunks
                else 0,
            }
        )
    return rows
