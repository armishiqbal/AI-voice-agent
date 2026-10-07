from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4

from PIL import Image

from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.database import Base, SessionLocal, engine
from app.repositories.records import PropertyMediaRecord, PropertyRecord
from app.workers.media import MediaProcessingWorker, strip_exif_and_generate_webp


def _create_image_with_exif() -> bytes:
    """Create a JPEG with explicit Camera EXIF metadata using native Pillow."""
    img = Image.new("RGB", (1600, 1200), color=(34, 139, 34))

    # Synthetic EXIF payload using native Pillow
    exif = img.getexif()
    exif[0x010F] = "Awaaz Camera"  # Make
    exif[0x0110] = "Drone-4K"  # Model
    exif[0x0131] = "Proprietary"  # Software

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def test_strip_exif_and_generate_webp() -> None:
    raw_with_exif = _create_image_with_exif()

    # Confirm raw image has EXIF metadata
    with Image.open(io.BytesIO(raw_with_exif)) as raw_img:
        exif = raw_img.getexif()
        assert exif.get(0x010F) == "Awaaz Camera"
        assert exif.get(0x0110) == "Drone-4K"

    # Strip and generate WebP derivative
    webp_bytes = strip_exif_and_generate_webp(raw_with_exif, max_dimensions=(800, 600), quality=80)
    assert len(webp_bytes) > 0

    with Image.open(io.BytesIO(webp_bytes)) as processed_img:
        assert processed_img.format == "WEBP"
        assert processed_img.width <= 800
        assert processed_img.height <= 600
        # Assert complete absence of EXIF metadata in processed derivative
        assert len(processed_img.getexif()) == 0


def test_media_processing_worker_lifecycle(tmp_path: Path) -> None:
    Base.metadata.drop_all(bind=engine)
    create_schema_for_local_development()

    # 1. Write an original photo with EXIF to disk
    original_file = tmp_path / "original_house.jpg"
    original_file.write_bytes(_create_image_with_exif())

    property_id = f"PROP-{uuid4().hex[:6]}"
    media_id = str(uuid4())

    with SessionLocal.begin() as session:
        session.add(
            PropertyRecord(
                id=property_id,
                title="Clifton Luxury Villa",
                city="Karachi",
                area="Clifton",
                purpose="sale",
                price_pkr=85_000_000,
                bedrooms=4,
                size_sqft=4500,
                amenities=["Garden", "Pool"],
                developer="Private",
                payment_plan="Cash",
                available=True,
                assigned_employee="Ayesha Khan",
                source_version="v1",
                slug=f"clifton-luxury-villa-{property_id.lower()}",
                transaction_type="sale",
                property_type="house",
                publication_status="draft",
                availability_status="available",
            )
        )
        session.add(
            PropertyMediaRecord(
                id=media_id,
                property_id=property_id,
                original_object_path=str(original_file),
                derivative_object_path=None,
                public_url=None,
                alt_text="Front elevation",
                sort_order=0,
                processing_status="pending",
                is_public=False,
            )
        )

    # 2. Run the media worker
    derivatives_dir = tmp_path / "derivatives"
    worker = MediaProcessingWorker(storage_dir=derivatives_dir)
    processed_count = worker.process_pending(limit=10)
    assert processed_count == 1

    # 3. Verify record was updated in database
    with SessionLocal() as session:
        media = session.get(PropertyMediaRecord, media_id)
        assert media is not None
        assert media.processing_status == "ready"
        assert media.is_public is False  # Processing cannot grant publication permission
        assert media.derivative_object_path is not None
        assert media.public_url is not None
        assert media.public_url.endswith(f"{media_id}_card.webp")

        # 4. Verify file on disk is valid WebP with EXIF stripped
        generated_file = Path(media.derivative_object_path)
        assert generated_file.is_file()
        with Image.open(generated_file) as derivative_img:
            assert derivative_img.format == "WEBP"
            assert "exif" not in derivative_img.info

    Base.metadata.drop_all(bind=engine)
