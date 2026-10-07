"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useShortlist } from "@/lib/favorites";

export function ShortlistBadge() {
  const pathname = usePathname();
  const { ready, count } = useShortlist();
  const active = pathname === "/shortlist";

  return (
    <Link
      href="/shortlist"
      className={`shortlist-nav-link ${active ? "active" : ""}`}
      aria-label={ready && count > 0 ? `Saved properties, ${count} items` : "Saved properties"}
      aria-current={active ? "page" : undefined}
    >
      <svg
        viewBox="0 0 24 24"
        width="16"
        height="16"
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
      </svg>
      <span>Saved</span>
      {ready && count > 0 && <span className="shortlist-badge-pill">{count}</span>}
    </Link>
  );
}
