"use client";

import { useState, useEffect, useCallback } from "react";
import { type Photo, photoUrl } from "@/lib/catalog";

interface PropertyPhotoMosaicProps {
  photos: Photo[];
  title: string;
}

export function PropertyPhotoMosaic({ photos, title }: PropertyPhotoMosaicProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  const validPhotos = photos
    .map((p) => ({ ...p, validUrl: photoUrl(p.url) }))
    .filter((p): p is Photo & { validUrl: string } => !!p.validUrl);

  const total = validPhotos.length;

  const openLightbox = (index: number) => {
    setCurrentIndex(index);
    setLightboxOpen(true);
  };

  const closeLightbox = () => {
    setLightboxOpen(false);
  };

  const nextPhoto = useCallback(() => {
    if (total <= 1) return;
    setCurrentIndex((prev) => (prev + 1) % total);
  }, [total]);

  const prevPhoto = useCallback(() => {
    if (total <= 1) return;
    setCurrentIndex((prev) => (prev - 1 + total) % total);
  }, [total]);

  // Keyboard navigation for lightbox
  useEffect(() => {
    if (!lightboxOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowRight") nextPhoto();
      if (e.key === "ArrowLeft") prevPhoto();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [lightboxOpen, nextPhoto, prevPhoto]);

  // 0 photos fallback
  if (total === 0) {
    return (
      <div className="photo-mosaic-empty">
        <div className="empty-photo-card">
          <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
          <p className="empty-photo-title">Official Photographs Under Verification</p>
          <p className="empty-photo-sub">Site survey photos and architectural floorplans are currently being cataloged by our verification team.</p>
        </div>
      </div>
    );
  }

  // 1 photo layout
  if (total === 1) {
    return (
      <>
        <div className="photo-mosaic-single">
          <button
            type="button"
            className="mosaic-single-item"
            onClick={() => openLightbox(0)}
            aria-label="View photo in fullscreen"
          >
            <img
              src={validPhotos[0].validUrl}
              alt={validPhotos[0].alt_text || title}
              className="mosaic-img"
            />
            <span className="view-all-pill">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21 15 16 10 5 21" />
              </svg>
              View Fullscreen
            </span>
          </button>
        </div>
        {lightboxOpen && renderLightboxModal()}
      </>
    );
  }

  // 2 photos layout
  if (total === 2) {
    return (
      <>
        <div className="photo-mosaic-duo">
          {validPhotos.map((photo, i) => (
            <button
              key={`${photo.validUrl}-${i}`}
              type="button"
              className="mosaic-duo-item"
              onClick={() => openLightbox(i)}
            >
              <img
                src={photo.validUrl}
                alt={photo.alt_text || `${title} photo ${i + 1}`}
                className="mosaic-img"
              />
            </button>
          ))}
          <button type="button" className="view-all-pill" onClick={() => openLightbox(0)}>
            View All {total} Photos
          </button>
        </div>
        {lightboxOpen && renderLightboxModal()}
      </>
    );
  }

  // 3 or 4 photos layout
  if (total === 3 || total === 4) {
    return (
      <>
        <div className="photo-mosaic-split">
          <button
            type="button"
            className="mosaic-hero-item"
            onClick={() => openLightbox(0)}
          >
            <img
              src={validPhotos[0].validUrl}
              alt={validPhotos[0].alt_text || title}
              className="mosaic-img"
            />
          </button>
          <div className="mosaic-secondary-stack">
            {validPhotos.slice(1, total).map((photo, idx) => (
              <button
                key={`${photo.validUrl}-${idx}`}
                type="button"
                className="mosaic-sub-item"
                onClick={() => openLightbox(idx + 1)}
              >
                <img
                  src={photo.validUrl}
                  alt={photo.alt_text || `${title} photo ${idx + 2}`}
                  className="mosaic-img"
                />
              </button>
            ))}
          </div>
          <button type="button" className="view-all-pill" onClick={() => openLightbox(0)}>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="14" width="7" height="7" rx="1" />
              <rect x="3" y="14" width="7" height="7" rx="1" />
            </svg>
            Show All {total} Photos
          </button>
        </div>
        {lightboxOpen && renderLightboxModal()}
      </>
    );
  }

  // 5+ photos layout: 1 Hero on left (60%), 2x2 grid on right (40%)
  const heroPhoto = validPhotos[0];
  const sidePhotos = validPhotos.slice(1, 5);
  const remainingCount = total - 5;

  return (
    <>
      <div className="photo-mosaic-grid">
        {/* Left Hero (60%) */}
        <button
          type="button"
          className="mosaic-grid-hero"
          onClick={() => openLightbox(0)}
          aria-label="View photo 1 in fullscreen"
        >
          <img
            src={heroPhoto.validUrl}
            alt={heroPhoto.alt_text || title}
            className="mosaic-img"
          />
          <span className="mosaic-audit-tag">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Physical On-Site Photography
          </span>
        </button>

        {/* Right 2x2 Grid (40%) */}
        <div className="mosaic-grid-quad">
          {sidePhotos.map((photo, idx) => {
            const actualIndex = idx + 1;
            const isLast = idx === 3 && remainingCount > 0;

            return (
              <button
                key={`${photo.validUrl}-${idx}`}
                type="button"
                className="mosaic-quad-item"
                onClick={() => openLightbox(actualIndex)}
                aria-label={`View photo ${actualIndex + 1}`}
              >
                <img
                  src={photo.validUrl}
                  alt={photo.alt_text || `${title} photo ${actualIndex + 1}`}
                  className="mosaic-img"
                />
                {isLast && (
                  <div className="mosaic-overlay-more">
                    <span>+{remainingCount} Photos</span>
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* Floating Lightbox Trigger Pill */}
        <button
          type="button"
          className="view-all-pill"
          onClick={() => openLightbox(0)}
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
          </svg>
          Show All {total} Photos
        </button>
      </div>

      {lightboxOpen && renderLightboxModal()}
    </>
  );

  function renderLightboxModal() {
    const currentPhoto = validPhotos[currentIndex];

    return (
      <div className="lightbox-overlay" role="dialog" aria-modal="true" aria-label="Photo gallery lightbox">
        {/* Backdrop click to close */}
        <div className="lightbox-backdrop" onClick={closeLightbox} />

        <div className="lightbox-modal">
          {/* Header Bar */}
          <div className="lightbox-header">
            <div className="lightbox-counter">
              <span className="counter-current">{currentIndex + 1}</span>
              <span className="counter-divider">/</span>
              <span className="counter-total">{total}</span>
              <span className="counter-title">{title}</span>
            </div>
            <button
              type="button"
              className="lightbox-close-btn"
              onClick={closeLightbox}
              title="Close gallery (Esc)"
              aria-label="Close gallery"
            >
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          {/* Main Stage Image */}
          <div className="lightbox-stage">
            {total > 1 && (
              <button
                type="button"
                className="lightbox-nav-btn prev"
                onClick={prevPhoto}
                aria-label="Previous photo"
              >
                <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="15 18 9 12 15 6" />
                </svg>
              </button>
            )}

            <div className="lightbox-image-wrapper">
              <img
                src={currentPhoto.validUrl}
                alt={currentPhoto.alt_text || `${title} photo ${currentIndex + 1}`}
                className="lightbox-main-img"
              />
              {currentPhoto.alt_text && (
                <p className="lightbox-caption">{currentPhoto.alt_text}</p>
              )}
            </div>

            {total > 1 && (
              <button
                type="button"
                className="lightbox-nav-btn next"
                onClick={nextPhoto}
                aria-label="Next photo"
              >
                <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
            )}
          </div>

          {/* Bottom Thumbnails Carousel */}
          {total > 1 && (
            <div className="lightbox-thumbnails">
              {validPhotos.map((photo, i) => (
                <button
                  key={`${photo.validUrl}-${i}`}
                  type="button"
                  className={`thumb-btn ${i === currentIndex ? "active" : ""}`}
                  onClick={() => setCurrentIndex(i)}
                  aria-label={`Go to photo ${i + 1}`}
                >
                  <img src={photo.validUrl} alt="" width="60" height="40" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }
}
