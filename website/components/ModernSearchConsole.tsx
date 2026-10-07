"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";

interface SectorOption {
  id: string;
  name: string;
  city: string;
  category: "Capital Sector" | "Gated Community";
  highlight?: string;
}

const SECTOR_OPTIONS: SectorOption[] = [
  { id: "f-7", name: "Sector F-7", city: "Islamabad", category: "Capital Sector", highlight: "Margalla Vistas & Diplomatic Core" },
  { id: "f-6", name: "Sector F-6", city: "Islamabad", category: "Capital Sector", highlight: "Super Market & Embassies" },
  { id: "f-8", name: "Sector F-8", city: "Islamabad", category: "Capital Sector", highlight: "Centaurus & Judicial Complex" },
  { id: "f-10", name: "Sector F-10", city: "Islamabad", category: "Capital Sector", highlight: "Commercial Center & Parks" },
  { id: "e-7", name: "Sector E-7", city: "Islamabad", category: "Capital Sector", highlight: "Exclusive Margalla Foothills" },
  { id: "e-11", name: "Sector E-11", city: "Islamabad", category: "Capital Sector", highlight: "Luxury Penthouses & Towers" },
  { id: "blue-area", name: "Blue Area", city: "Islamabad", category: "Capital Sector", highlight: "Central Business District" },
  { id: "dha-2", name: "DHA Phase 2", city: "Islamabad", category: "Gated Community", highlight: "Giga Mall Corridor & Gated Security" },
  { id: "bahria-7", name: "Bahria Town Phase 7", city: "Rawalpindi", category: "Gated Community", highlight: "River View & Civic Amenities" },
  { id: "gulberg", name: "Gulberg Greens", city: "Islamabad", category: "Gated Community", highlight: "Agro Farmhouses & Expressway" },
];

export function ModernSearchConsole() {
  const router = useRouter();
  const [tab, setTab] = useState<"sale" | "rent">("sale");
  const [selectedCity, setSelectedCity] = useState<string>("");
  const [query, setQuery] = useState("");
  const [propertyType, setPropertyType] = useState("");
  const [priceRange, setPriceRange] = useState("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredSectors = SECTOR_OPTIONS.filter((item) => {
    const matchesCity = !selectedCity || item.city.toLowerCase() === selectedCity.toLowerCase();
    const matchesQuery =
      !query.trim() ||
      item.name.toLowerCase().includes(query.toLowerCase()) ||
      item.city.toLowerCase().includes(query.toLowerCase()) ||
      (item.highlight && item.highlight.toLowerCase().includes(query.toLowerCase()));
    return matchesCity && matchesQuery;
  });

  const handleSelectSector = (sector: SectorOption) => {
    setQuery(sector.name);
    setSelectedCity(sector.city);
    setIsDropdownOpen(false);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams();
    if (tab) params.set("transaction_type", tab);
    if (selectedCity) params.set("city", selectedCity);
    if (query.trim()) params.set("q", query.trim());
    if (propertyType) params.set("property_type", propertyType);

    if (tab === "sale") {
      if (priceRange === "under-1cr") {
        params.set("max_price_pkr", "10000000");
      } else if (priceRange === "1cr-3cr") {
        params.set("min_price_pkr", "10000000");
        params.set("max_price_pkr", "30000000");
      } else if (priceRange === "3cr-7cr") {
        params.set("min_price_pkr", "30000000");
        params.set("max_price_pkr", "70000000");
      } else if (priceRange === "7cr-15cr") {
        params.set("min_price_pkr", "70000000");
        params.set("max_price_pkr", "150000000");
      } else if (priceRange === "above-15cr") {
        params.set("min_price_pkr", "150000000");
      }
    } else {
      if (priceRange === "under-1l") {
        params.set("max_price_pkr", "100000");
      } else if (priceRange === "1l-2.5l") {
        params.set("min_price_pkr", "100000");
        params.set("max_price_pkr", "250000");
      } else if (priceRange === "2.5l-5l") {
        params.set("min_price_pkr", "250000");
        params.set("max_price_pkr", "500000");
      } else if (priceRange === "5l-10l") {
        params.set("min_price_pkr", "500000");
        params.set("max_price_pkr", "1000000");
      } else if (priceRange === "above-10l") {
        params.set("min_price_pkr", "1000000");
      }
    }

    router.push(`/properties?${params.toString()}`);
  };

  const trendingSearches = [
    { label: "F-7 Islamabad", q: "F-7", city: "Islamabad" },
    { label: "DHA Phase 2", q: "DHA Phase 2", city: "Islamabad" },
    { label: "Bahria Phase 7", q: "Bahria Town Phase 7", city: "Rawalpindi" },
    { label: "Gulberg Greens", q: "Gulberg Greens", city: "Islamabad" },
    { label: "E-11 Penthouses", q: "E-11", city: "Islamabad" },
  ];

  return (
    <div className="modern-search-wrapper" ref={containerRef}>
      {/* Top Segmented Tabs: Buy vs Rent */}
      <div className="search-tabs" role="tablist" aria-label="Transaction type">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "sale"}
          className={`search-tab ${tab === "sale" ? "active" : ""}`}
          onClick={() => {
            setTab("sale");
            setPriceRange("");
          }}
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ marginRight: 6 }}>
            <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          </svg>
          Buy Property
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "rent"}
          className={`search-tab ${tab === "rent" ? "active" : ""}`}
          onClick={() => {
            setTab("rent");
            setPriceRange("");
          }}
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ marginRight: 6 }}>
            <rect width="18" height="18" x="3" y="3" rx="2" />
            <path d="M3 9h18M9 21V9" />
          </svg>
          Rent Property
        </button>
      </div>

      {/* Unified 4-Cell Search Console Grid */}
      <form onSubmit={handleSearch} className="modern-search-bar">
        {/* Cell 1: Location or Sector */}
        <div className="search-cell location-cell">
          <label htmlFor="search-location" className="cell-label">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            Location or Sector
          </label>
          <div className="input-with-clear">
            <input
              id="search-location"
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setIsDropdownOpen(true);
              }}
              onFocus={() => setIsDropdownOpen(true)}
              placeholder="e.g. F-7, DHA Phase 2, Bahria..."
              className="cell-input borderless"
              autoComplete="off"
            />
            {query && (
              <button
                type="button"
                className="input-clear-btn"
                onClick={() => setQuery("")}
                aria-label="Clear location input"
              >
                ×
              </button>
            )}
          </div>

          {/* Autocomplete Dropdown Popover */}
          {isDropdownOpen && (
            <div className="luxury-autocomplete-panel" role="listbox">
              <div className="autocomplete-header">
                <span>Verified Sectors &amp; Communities</span>
                <span className="autocomplete-count">{filteredSectors.length} found</span>
              </div>
              <div className="autocomplete-list">
                {filteredSectors.length > 0 ? (
                  filteredSectors.map((sector) => (
                    <button
                      key={sector.id}
                      type="button"
                      className="autocomplete-item"
                      onClick={() => handleSelectSector(sector)}
                    >
                      <div className="item-pin-box" aria-hidden="true">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z" />
                          <circle cx="12" cy="10" r="3" />
                        </svg>
                      </div>
                      <div className="item-text">
                        <div className="item-title-row">
                          <span className="item-name">{sector.name}</span>
                          <span className="item-city-badge">{sector.city}</span>
                        </div>
                        {sector.highlight && (
                          <span className="item-highlight">{sector.highlight}</span>
                        )}
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="autocomplete-empty">
                    <span>Press Enter to search for &ldquo;{query}&rdquo;</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="search-divider" aria-hidden="true" />

        {/* Cell 2: City Dropdown */}
        <div className="search-cell">
          <label htmlFor="search-city" className="cell-label">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <rect width="18" height="18" x="3" y="3" rx="2" />
              <path d="M3 9h18M9 21V9" />
            </svg>
            City
          </label>
          <select
            id="search-city"
            value={selectedCity}
            onChange={(e) => setSelectedCity(e.target.value)}
            className="cell-select"
          >
            <option value="">All Cities</option>
            <option value="Islamabad">Islamabad</option>
            <option value="Rawalpindi">Rawalpindi</option>
          </select>
        </div>

        <div className="search-divider" aria-hidden="true" />

        {/* Cell 3: Property Type Dropdown */}
        <div className="search-cell">
          <label htmlFor="search-type" className="cell-label">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
              <polyline points="9 22 9 12 15 12 15 22" />
            </svg>
            Property Type
          </label>
          <select
            id="search-type"
            value={propertyType}
            onChange={(e) => setPropertyType(e.target.value)}
            className="cell-select"
          >
            <option value="">All Types</option>
            <option value="house">House / Villa</option>
            <option value="apartment">Apartment / Flat</option>
            <option value="plot">Residential Plot</option>
            <option value="office">Commercial Office</option>
            <option value="shop">Retail Shop</option>
          </select>
        </div>

        <div className="search-divider" aria-hidden="true" />

        {/* Cell 4: Budget Range Dropdown */}
        <div className="search-cell">
          <label htmlFor="search-budget" className="cell-label">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 6v12M15 9.5a3 3 0 0 0-6 0c0 3 6 2 6 5a3 3 0 0 1-6 0" />
            </svg>
            {tab === "sale" ? "Price Budget" : "Monthly Rent"}
          </label>
          <select
            id="search-budget"
            value={priceRange}
            onChange={(e) => setPriceRange(e.target.value)}
            className="cell-select"
          >
            <option value="">Any Budget</option>
            {tab === "sale" ? (
              <>
                <option value="under-1cr">Under 1 Crore</option>
                <option value="1cr-3cr">1 to 3 Crore</option>
                <option value="3cr-7cr">3 to 7 Crore</option>
                <option value="7cr-15cr">7 to 15 Crore</option>
                <option value="above-15cr">15+ Crore</option>
              </>
            ) : (
              <>
                <option value="under-1l">Under 1 Lakh / mo</option>
                <option value="1l-2.5l">1 to 2.5 Lakh / mo</option>
                <option value="2.5l-5l">2.5 to 5 Lakh / mo</option>
                <option value="5l-10l">5 to 10 Lakh / mo</option>
                <option value="above-10l">Above 10 Lakh / mo</option>
              </>
            )}
          </select>
        </div>

        {/* Submit Search Button */}
        <button type="submit" className="modern-search-btn">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span>{tab === "sale" ? "Search Properties" : "Search Rentals"}</span>
        </button>
      </form>

      {/* Trending Quick Search Chips */}
      <div className="search-chips">
        <span className="chips-label">Popular Sectors:</span>
        <div className="chips-list">
          {trendingSearches.map((item) => (
            <button
              key={item.label}
              type="button"
              className={`search-chip ${query === item.q ? "active" : ""}`}
              onClick={() => {
                setQuery(item.q);
                setSelectedCity(item.city);
                router.push(`/properties?q=${encodeURIComponent(item.q)}&city=${encodeURIComponent(item.city)}&transaction_type=${tab}`);
              }}
            >
              <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ marginRight: 4, display: "inline-block" }}>
                <path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z" />
              </svg>
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
