"use client";

import { useEffect, useId, useState } from "react";

type Location = { id: string; city: string; area: string; label: string };

function isLocation(value: unknown): value is Location {
  if (typeof value !== "object" || value === null) return false;
  const row = value as Record<string, unknown>;
  return ["id", "city", "area", "label"].every((key) => typeof row[key] === "string");
}

export function LocationInput({ initialCity = "", initialArea = "" }: { initialCity?: string; initialArea?: string }) {
  const [city, setCity] = useState(initialCity);
  const [query, setQuery] = useState(initialArea);
  const [locations, setLocations] = useState<Location[]>([]);
  const listId = useId();

  useEffect(() => {
    const select = document.getElementById("search-city");
    if (!(select instanceof HTMLSelectElement)) return;
    const updateCity = () => setCity(select.value);
    updateCity();
    select.addEventListener("change", updateCity);
    return () => select.removeEventListener("change", updateCity);
  }, []);

  useEffect(() => {
    const search = query.trim();
    if (search.length < 2) {
      setLocations([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({ q: search });
      if (city) params.set("city", city);
      void fetch(`/api/public/locations?${params}`, { signal: controller.signal })
        .then(async (response) => {
          if (!response.ok) return null;
          const body: unknown = await response.json();
          if (typeof body !== "object" || body === null || !("data" in body) || !Array.isArray(body.data)) return null;
          return body.data.every(isLocation) ? body.data : null;
        })
        .then((data) => { if (!controller.signal.aborted) setLocations(data ?? []); })
        .catch(() => { if (!controller.signal.aborted) setLocations([]); });
    }, 200);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [city, query]);

  return <>
    <input
      name="area"
      list={listId}
      value={query}
      onChange={(event) => setQuery(event.target.value)}
      placeholder="Start typing a reviewed area"
      maxLength={128}
      autoComplete="off"
      aria-describedby={`${listId}-hint`}
    />
    <datalist id={listId}>{locations.map((location) => <option key={location.id} value={location.label} />)}</datalist>
    <small id={`${listId}-hint`} aria-live="polite">{city ? `Area suggestions for ${city}.` : "Area suggestions include their city; you can also search all cities."}</small>
  </>;
}
