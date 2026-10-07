"use client";

import { useEffect, useState, useCallback } from "react";

export const COMPARE_STORAGE_KEY = "awaaz_guest_compare";
export const COMPARE_CHANGE_EVENT = "awaaz:compare:changed";

export interface CompareItem {
  slug: string;
  title: string;
  price_pkr?: number;
  photo_url?: string | null;
  property_type?: string;
  area?: string;
  city?: string;
}

/**
 * Safely retrieves comparison items from localStorage.
 */
export function getStoredCompare(): CompareItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(COMPARE_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is CompareItem =>
        Boolean(item) && typeof item.slug === "string" && item.slug.trim().length > 0
    ).slice(0, 3);
  } catch {
    return [];
  }
}

/**
 * Persists comparison items to localStorage and dispatches a broadcast event.
 */
export function setStoredCompare(items: CompareItem[]): void {
  if (typeof window === "undefined") return;
  const valid = items.filter(
    (item): item is CompareItem =>
      Boolean(item) && typeof item.slug === "string" && item.slug.trim().length > 0
  ).slice(0, 3);
  try {
    window.localStorage.setItem(COMPARE_STORAGE_KEY, JSON.stringify(valid));
  } catch (err) {
    console.warn("Unable to save comparison to localStorage:", err);
  }
  window.dispatchEvent(new CustomEvent(COMPARE_CHANGE_EVENT, { detail: valid }));
}

/**
 * Checks if a property slug is in the comparison tray.
 */
export function isInCompare(slug: string): boolean {
  if (!slug) return false;
  return getStoredCompare().some((item) => item.slug === slug);
}

/**
 * Toggles a property in the comparison tray.
 * Max 3 items permitted.
 */
export function toggleCompare(item: CompareItem): { added: boolean; limitReached: boolean } {
  if (!item || !item.slug) return { added: false, limitReached: false };
  const current = getStoredCompare();
  const exists = current.some((p) => p.slug === item.slug);

  if (exists) {
    const updated = current.filter((p) => p.slug !== item.slug);
    setStoredCompare(updated);
    return { added: false, limitReached: false };
  }

  if (current.length >= 3) {
    return { added: false, limitReached: true };
  }

  setStoredCompare([...current, item]);
  return { added: true, limitReached: false };
}

/**
 * Removes a property slug from the comparison tray.
 */
export function removeFromCompare(slug: string): void {
  if (!slug) return;
  const current = getStoredCompare();
  setStoredCompare(current.filter((item) => item.slug !== slug));
}

/**
 * Clears all comparison items.
 */
export function clearCompare(): void {
  setStoredCompare([]);
}

/**
 * React hook to subscribe to real-time changes to the comparison tray.
 */
export function useCompare() {
  const [ready, setReady] = useState(false);
  const [items, setItems] = useState<CompareItem[]>([]);

  useEffect(() => {
    setItems(getStoredCompare());
    setReady(true);

    const handleCustomChange = (e: Event) => {
      const detail = (e as CustomEvent<CompareItem[]>).detail;
      if (Array.isArray(detail)) {
        setItems(detail);
      } else {
        setItems(getStoredCompare());
      }
    };

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === COMPARE_STORAGE_KEY) {
        setItems(getStoredCompare());
      }
    };

    window.addEventListener(COMPARE_CHANGE_EVENT, handleCustomChange);
    window.addEventListener("storage", handleStorageChange);

    return () => {
      window.removeEventListener(COMPARE_CHANGE_EVENT, handleCustomChange);
      window.removeEventListener("storage", handleStorageChange);
    };
  }, []);

  const has = useCallback((slug: string) => items.some((item) => item.slug === slug), [items]);
  const toggle = useCallback((item: CompareItem) => toggleCompare(item), []);
  const remove = useCallback((slug: string) => removeFromCompare(slug), []);
  const clear = useCallback(() => clearCompare(), []);

  return {
    ready,
    items,
    count: items.length,
    has,
    toggle,
    remove,
    clear,
  };
}
