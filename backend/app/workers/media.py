from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from PIL import Image
from sqlalchemy import select

from app.core.config import settings
from app.repositories.database import SessionLocal
from app.repositories.records import PropertyMediaRecord

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger("awaaz.media_worker")

DEFAULT_DERIVATIVE_SIZES = {
    "thumbnail": (400, 300),
    "card": (800, 600),
    "hero": (1600, 1200),
}


def strip_exif_and_generate_webp(
    raw_bytes: bytes,
    max_dimensions: tuple[int, int] = (800, 600),
    quality: int = 82,
) -> bytes:
    """Strips all EXIF/GPS/camera metadata and converts to optimized WebP format."""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        if img.width * img.height > 20_000_000:
            raise ValueError("Photo dimensions exceed limit")
        # Convert color formats properly
        if img.mode in ("RGBA", "LA", "P"):
            converted = img.convert("RGBA")
        else:
            converted = img.convert("RGB")

        # Create a completely clean image without preserving any EXIF/metadata dictionary
        clean = Image.new(converted.mode, converted.size)
        clean.paste(converted)
        clean.info.pop("exif", None)

        # Scale down to target dimensions preserving aspect ratio
        clean.thumbnail(max_dimensions, Image.Resampling.LANCZOS)

        out_buffer = io.BytesIO()
        clean.save(out_buffer, format="WEBP", quality=quality, method=6)
        return out_buffer.getvalue()


class MediaProcessingWorker:
    """Processes pending property media records, stripping EXIF and generating WebP derivatives."""

    def __init__(
        self,
        session_factory=SessionLocal,
        storage_dir: Path | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.storage_dir = (
            storage_dir
            if storage_dir is not None
            else Path(__file__).parents[3] / "media" / "derivatives"
        )
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _read_original_bytes(self, path_or_url: str) -> bytes:
        if path_or_url.startswith("supabase:"):
            if not settings.supabase_url or not settings.supabase_service_role_key:
                raise RuntimeError("Private storage is not configured")
            path = path_or_url.removeprefix("supabase:")
            with httpx.stream(
                "GET",
                f"{settings.supabase_url.rstrip('/')}/storage/v1/object/property-originals/{path}",
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "apikey": settings.supabase_service_role_key,
                },
                timeout=20,
            ) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    if len(data) + len(chunk) > 8 * 1024 * 1024:
                        raise ValueError("Original exceeds photo size limit")
                    data.extend(chunk)
                return bytes(data)
        local_path = Path(path_or_url)
        if local_path.is_file():
            return local_path.read_bytes()

        # If it's a relative path in workspace
        candidate = Path(__file__).parents[3] / path_or_url.lstrip("/")
        if candidate.is_file():
            return candidate.read_bytes()

        raise FileNotFoundError(f"Original media file not found: {path_or_url}")

    def process_record(self, record: PropertyMediaRecord, session: Session) -> bool:
        try:
            raw_bytes = self._read_original_bytes(record.original_object_path)
            webp_bytes = strip_exif_and_generate_webp(
                raw_bytes,
                max_dimensions=DEFAULT_DERIVATIVE_SIZES["card"],
                quality=82,
            )

            with Image.open(io.BytesIO(raw_bytes)) as original:
                if original.width * original.height > 20_000_000:
                    raise ValueError("Photo dimensions exceed limit")
            derivative_filename = f"{record.id}_card.webp"
            derivative_file = self.storage_dir / derivative_filename
            derivative_file.write_bytes(webp_bytes)

            if record.original_object_path.startswith("supabase:"):
                storage_path = record.original_object_path.removeprefix("supabase:") + ".webp"
                r = httpx.post(
                    f"{settings.supabase_url.rstrip('/')}/storage/v1/object/property-processed/{storage_path}",
                    headers={
                        "Authorization": f"Bearer {settings.supabase_service_role_key}",
                        "apikey": settings.supabase_service_role_key,
                        "content-type": "image/webp",
                        "x-upsert": "true",
                    },
                    content=webp_bytes,
                    timeout=20,
                )
                r.raise_for_status()
                record.derivative_object_path = "supabase:" + storage_path
            else:
                record.derivative_object_path = str(derivative_file)
            public_base = (getattr(settings, "site_url", None) or "").rstrip("/")
            if public_base:
                record.public_url = f"{public_base}/media/derivatives/{derivative_filename}"
            else:
                record.public_url = f"/media/derivatives/{derivative_filename}"

            if record.original_object_path.startswith("supabase:"):
                record.public_url = None
            record.processing_status = "ready"
            record.is_public = False
            logger.info("Processed media record %s to %s", record.id, derivative_filename)
            return True
        except (OSError, ValueError, RuntimeError, httpx.HTTPError, Image.DecompressionBombError):
            logger.error("Failed to process media record %s", record.id)
            record.processing_status = "failed"
            return False

    def process_pending(self, limit: int = 20) -> int:
        processed_count = 0
        with self.session_factory.begin() as session:
            pending_records = session.scalars(
                select(PropertyMediaRecord)
                .where(PropertyMediaRecord.processing_status == "pending")
                .limit(limit)
            ).all()

            for record in pending_records:
                success = self.process_record(record, session)
                if success:
                    processed_count += 1

        return processed_count
