"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { type SectorDossierMeta, type CivicCategory } from "@/lib/sectors";

interface AreasExplorerProps {
  initialSectors: SectorDossierMeta[];
}

const categoryLabels: Record<Exclude<CivicCategory, "all">, string> = {
  cda: "Residential sectors",
  gated: "Gated communities",
  agro: "Farm living",
  commercial: "Commercial areas",
  waterfront: "Waterfront communities",
};

export function AreasExplorer({ initialSectors }: AreasExplorerProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCity, setSelectedCity] = useState("all");
  const [selectedCategory, setSelectedCategory] = useState<CivicCategory>("all");

  const cities = useMemo(
    () => Array.from(new Set(initialSectors.map((sector) => sector.city))).sort(),
    [initialSectors],
  );
  const categories = useMemo(
    () => Array.from(new Set(initialSectors.map((sector) => sector.category)))
      .filter((category): category is Exclude<CivicCategory, "all"> => category !== "all"),
    [initialSectors],
  );

  const filteredSectors = useMemo(() => {
    const query = searchQuery.trim().toLocaleLowerCase();
    return initialSectors.filter((sector) => {
      const matchesCity = selectedCity === "all" || sector.city === selectedCity;
      const matchesCategory = selectedCategory === "all" || sector.category === selectedCategory;
      const searchableText = [
        sector.area,
        sector.title,
        sector.city,
        sector.description,
        sector.lifestyle,
        sector.categoryLabel,
        ...sector.keyHighlights,
      ].join(" ").toLocaleLowerCase();
      return matchesCity && matchesCategory && (!query || searchableText.includes(query));
    });
  }, [initialSectors, searchQuery, selectedCity, selectedCategory]);

  const hasFilters = searchQuery.trim() !== "" || selectedCity !== "all" || selectedCategory !== "all";
  const resetFilters = () => {
    setSearchQuery("");
    setSelectedCity("all");
    setSelectedCategory("all");
  };

  return (
    <div className="areas-explorer-v2">
      <div className="areas-filter-panel-v2">
        <label className="areas-search-wrap-v2">
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7.5" /><path d="m16.5 16.5 4 4" /></svg>
          <span className="sr-only">Search area guides</span>
          <input
            type="search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search an area, landmark, or lifestyle…"
          />
          {searchQuery && (
            <button type="button" onClick={() => setSearchQuery("")} aria-label="Clear area search">
              Clear
            </button>
          )}
        </label>

        <div className="areas-select-wrap-v2">
          <label htmlFor="areas-city-filter">City</label>
          <select id="areas-city-filter" value={selectedCity} onChange={(event) => setSelectedCity(event.target.value)}>
            <option value="all">All cities</option>
            {cities.map((city) => <option key={city} value={city}>{city}</option>)}
          </select>
        </div>

        <div className="areas-select-wrap-v2">
          <label htmlFor="areas-type-filter">Area type</label>
          <select
            id="areas-type-filter"
            value={selectedCategory}
            onChange={(event) => setSelectedCategory(event.target.value as CivicCategory)}
          >
            <option value="all">All area types</option>
            {categories.map((category) => (
              <option key={category} value={category}>{categoryLabels[category]}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="areas-results-row-v2" aria-live="polite">
        <p><strong>{filteredSectors.length}</strong> {filteredSectors.length === 1 ? "area guide" : "area guides"}</p>
        {hasFilters && <button type="button" onClick={resetFilters}>Clear filters</button>}
      </div>

      {filteredSectors.length > 0 ? (
        <div className="areas-grid-v2">
          {filteredSectors.map((sector) => {
            const guideUrl = `/areas/${sector.citySlug}/${sector.areaSlug}`;
            const catalogUrl = `/properties?city=${encodeURIComponent(sector.city)}&area=${encodeURIComponent(sector.area)}`;
            const typeLabel = categoryLabels[sector.category as Exclude<CivicCategory, "all">] ?? "Area guide";

            return (
              <article className="area-card-v2" key={sector.key}>
                <Link href={guideUrl} className="area-card-image-v2" aria-label={`Explore the ${sector.area} area guide`}>
                  <Image
                    src={sector.img}
                    alt={`${sector.area} area guide`}
                    fill
                    sizes="(max-width: 700px) 100vw, (max-width: 1100px) 50vw, 33vw"
                    style={{ objectFit: "cover" }}
                  />
                  <span className="area-card-city-v2">{sector.city}</span>
                </Link>

                <div className="area-card-body-v2">
                  <p className="area-card-type-v2">{typeLabel}</p>
                  <h3><Link href={guideUrl}>{sector.area}</Link></h3>
                  <p className="area-card-summary-v2">{sector.description}</p>

                  {sector.keyHighlights.length > 0 && (
                    <div className="area-card-highlights-v2" aria-label="Area highlights">
                      {sector.keyHighlights.slice(0, 2).map((highlight) => (
                        <span key={highlight}>{highlight}</span>
                      ))}
                    </div>
                  )}

                  <div className="area-card-actions-v2">
                    <Link href={guideUrl}>Read area guide <span aria-hidden="true">→</span></Link>
                    <Link href={catalogUrl}>View listings</Link>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="areas-empty-v2">
          <h3>No area guides match those filters.</h3>
          <p>Try another search or clear the filters to see all available guides.</p>
          <button type="button" onClick={resetFilters}>Show all area guides</button>
        </div>
      )}
    </div>
  );
}
