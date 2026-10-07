"use client";

import { useState } from "react";
import { useCompare, type CompareItem } from "@/lib/compare";

export function CompareButton({
  item,
  className = "",
}: {
  item: CompareItem;
  className?: string;
}) {
  const { has, toggle } = useCompare();
  const [notice, setNotice] = useState<string | null>(null);

  const active = has(item.slug);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const result = toggle(item);
    if (result.limitReached) {
      setNotice("Tray full (3 max)");
      setTimeout(() => setNotice(null), 2500);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`compare-toggle-btn ${active ? "active" : ""} ${className}`}
      aria-pressed={active}
      title={active ? "Remove from comparison tray" : "Add to comparison tray (max 3)"}
    >
      <svg
        viewBox="0 0 24 24"
        width="14"
        height="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        aria-hidden="true"
      >
        <path d="M16 3h5v5M4 20L20.2 3.8M21 16v5h-5M15 15l5.1 5.1M4 4l5 5" />
      </svg>
      <span>{notice || (active ? "In Compare" : "Compare")}</span>
    </button>
  );
}
