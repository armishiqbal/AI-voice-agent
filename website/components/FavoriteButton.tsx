"use client";

import React from "react";
import { useShortlist } from "@/lib/favorites";

type FavoriteButtonProps = {
  slug: string;
  title?: string;
  showLabel?: boolean;
  className?: string;
};

export function FavoriteButton({ slug, title, showLabel = false, className = "" }: FavoriteButtonProps) {
  const { ready, has, toggle } = useShortlist();
  const active = ready && has(slug);

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    toggle(slug);
  };

  const labelText = active ? "Saved to shortlist" : "Save to shortlist";
  const ariaLabel = active
    ? `Remove ${title || "property"} from shortlist`
    : `Save ${title || "property"} to shortlist`;

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-pressed={active}
      aria-label={ariaLabel}
      title={labelText}
      className={`favorite-btn ${active ? "active" : ""} ${showLabel ? "with-label" : ""} ${className}`.trim()}
    >
      <svg
        className="heart-icon"
        viewBox="0 0 24 24"
        width="20"
        height="20"
        aria-hidden="true"
        fill={active ? "#205c45" : "none"}
        stroke={active ? "#205c45" : "currentColor"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
      </svg>
      {showLabel && <span className="favorite-label">{labelText}</span>}
    </button>
  );
}
