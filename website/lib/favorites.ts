"use client";

import { useEffect, useState, useCallback } from "react";

export const SHORTLIST_STORAGE_KEY = "awaaz_guest_shortlist";
export const SHORTLIST_CHANGE_EVENT = "awaaz:shortlist:changed";

/**
 * Safely retrieves shortlisted slugs from localStorage.
 */
export function getStoredShortlist(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(SHORTLIST_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return [...new Set(parsed.filter((s): s is string => typeof s === "string" && s.trim().length > 0))];
  } catch {
    return [];
  }
}

/**
 * Persists shortlisted slugs to localStorage and dispatches a broadcast event.
 */
export function setStoredShortlist(slugs: string[]): void {
  if (typeof window === "undefined") return;
  const unique = [...new Set(slugs.filter((s): s is string => typeof s === "string" && s.trim().length > 0))];
  try {
    window.localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify(unique));
  } catch (err) {
    console.warn("Unable to save shortlist to localStorage:", err);
  }
  window.dispatchEvent(new CustomEvent(SHORTLIST_CHANGE_EVENT, { detail: unique }));
}

/**
 * Checks if a property slug is in the shortlist.
 */
export function isShortlisted(slug: string): boolean {
  if (!slug) return false;
  return getStoredShortlist().includes(slug);
}

/**
 * Toggles a property slug in the shortlist.
 * Returns true if added, false if removed.
 */
export function toggleShortlist(slug: string): boolean {
  if (!slug) return false;
  const current = getStoredShortlist();
  const exists = current.includes(slug);
  const updated = exists ? current.filter((s) => s !== slug) : [slug, ...current];
  setStoredShortlist(updated);
  return !exists;
}

/**
 * Adds a property slug to the shortlist.
 */
export function addToShortlist(slug: string): void {
  if (!slug) return;
  const current = getStoredShortlist();
  if (!current.includes(slug)) {
    setStoredShortlist([slug, ...current]);
  }
}

/**
 * Removes a property slug from the shortlist.
 */
export function removeFromShortlist(slug: string): void {
  if (!slug) return;
  const current = getStoredShortlist();
  if (current.includes(slug)) {
    setStoredShortlist(current.filter((s) => s !== slug));
  }
}

/**
 * Clears the shortlist.
 */
export function clearShortlist(): void {
  setStoredShortlist([]);
}

/**
 * React hook to subscribe to real-time changes to the guest shortlist.
 */
export function useShortlist() {
  const [ready, setReady] = useState(false);
  const [slugs, setSlugs] = useState<string[]>([]);

  useEffect(() => {
    setSlugs(getStoredShortlist());
    setReady(true);

    const handleCustomChange = (e: Event) => {
      const detail = (e as CustomEvent<string[]>).detail;
      if (Array.isArray(detail)) {
        setSlugs(detail);
      } else {
        setSlugs(getStoredShortlist());
      }
    };

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === SHORTLIST_STORAGE_KEY) {
        setSlugs(getStoredShortlist());
      }
    };

    window.addEventListener(SHORTLIST_CHANGE_EVENT, handleCustomChange);
    window.addEventListener("storage", handleStorageChange);

    return () => {
      window.removeEventListener(SHORTLIST_CHANGE_EVENT, handleCustomChange);
      window.removeEventListener("storage", handleStorageChange);
    };
  }, []);

  const has = useCallback((slug: string) => slugs.includes(slug), [slugs]);
  const toggle = useCallback((slug: string) => toggleShortlist(slug), []);
  const add = useCallback((slug: string) => addToShortlist(slug), []);
  const remove = useCallback((slug: string) => removeFromShortlist(slug), []);
  const clear = useCallback(() => clearShortlist(), []);

  return {
    ready,
    slugs,
    count: slugs.length,
    has,
    toggle,
    add,
    remove,
    clear,
  };
}
