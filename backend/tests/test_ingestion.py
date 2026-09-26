from __future__ import annotations

from app.services.ingestion import chunk_text, compare_chunk_sizes, parse_inventory_bytes


def test_csv_import_keeps_valid_rows_and_reports_invalid_rows() -> None:
    data = (
        b"id,title,city,area,purpose,price_pkr,bedrooms,size_sqft,amenities,developer,payment_plan,available,assigned_employee,source_version\n"
        b"P-1,House,Karachi,DHA Phase 6,sale,25000000,3,1800,parking|security,Dev,Installments,true,Ayesha,v1\n"
        b"P-2,Broken,Karachi,DHA Phase 6,sale,not-a-price,3,1800,parking,Dev,Installments,true,Ayesha,v1\n"
    )
    result = parse_inventory_bytes(data, "inventory.csv", "crm-export-2026-09-22")
    assert [item.id for item in result.records] == ["P-1"]
    assert result.records[0].source == "unverified"
    assert result.errors[0].field == "price_pkr"
    assert result.source == "crm-export-2026-09-22"


def test_json_import_accepts_properties_envelope() -> None:
    data = b'{"properties": [{"id":"P-1","title":"House","city":"Lahore","area":"Gulberg","purpose":"rent","price_pkr":100000,"bedrooms":2,"size_sqft":900,"amenities":[],"nearby_schools":["Model School"],"nearby_hospitals":["City Hospital"],"developer":"Dev","payment_plan":"Monthly","available":true,"assigned_employee":"Ali","source_version":"v1"}]}'
    result = parse_inventory_bytes(data, "inventory.json", "erp-v2")
    assert len(result.records) == 1
    assert result.records[0].city == "Lahore"
    assert result.records[0].nearby_hospitals == ["City Hospital"]
    assert result.errors == []


def test_chunking_preserves_source_and_overlap() -> None:
    chunks = chunk_text("a" * 1_000, "brochure.pdf", chunk_size=200, overlap=25)
    assert len(chunks) > 1
    assert all(chunk.metadata["source"] == "brochure.pdf" for chunk in chunks)
    assert chunks[0].text[-25:] == chunks[1].text[:25]


def test_chunk_size_comparison_is_reproducible() -> None:
    rows = compare_chunk_sizes("property details " * 200, "faq-v1", sizes=(200, 400))
    assert [row["chunk_size"] for row in rows] == [200, 400]
    assert rows[0]["chunk_count"] >= rows[1]["chunk_count"]
