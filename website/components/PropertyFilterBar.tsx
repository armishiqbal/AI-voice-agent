"use client";

import { useState, useEffect, useTransition } from "react";
import { useRouter, usePathname } from "next/navigation";
import { scalar, type SearchParams } from "@/lib/catalog";

interface PropertyFilterBarProps {
  params: SearchParams;
  totalResults?: number;
  currentView?: "grid" | "list" | "map";
  onViewChange?: (view: "grid" | "list" | "map") => void;
}

export function PropertyFilterBar({
  params,
  totalResults,
  currentView = "grid",
  onViewChange,
}: PropertyFilterBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [isPending, startTransition] = useTransition();

  // Local state initialized from URL params
  const [q, setQ] = useState(scalar(params.q));
  const [city, setCity] = useState<string>(scalar(params.city) || "");
  const [area, setArea] = useState<string>(scalar(params.area) || "");
  const [txType, setTxType] = useState<string>(scalar(params.transaction_type) || "");
  const [propType, setPropType] = useState<string>(scalar(params.property_type) || "");
  const [bedrooms, setBedrooms] = useState<string>(scalar(params.bedrooms) || "");
  const [sort, setSort] = useState<string>(scalar(params.sort) || "newest");
  const [minPrice, setMinPrice] = useState<string>(scalar(params.min_price_pkr) || "");
  const [maxPrice, setMaxPrice] = useState<string>(scalar(params.max_price_pkr) || "");
  const [minSize, setMinSize] = useState<string>(scalar(params.min_size_sqft) || "");
  const [maxSize, setMaxSize] = useState<string>(scalar(params.max_size_sqft) || "");
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Synchronize state when params change (e.g. back/forward navigation or external link clicks)
  useEffect(() => {
    setQ(scalar(params.q));
    setCity(scalar(params.city) || "");
    setArea(scalar(params.area) || "");
    setTxType(scalar(params.transaction_type) || "");
    setPropType(scalar(params.property_type) || "");
    setBedrooms(scalar(params.bedrooms) || "");
    setSort(scalar(params.sort) || "newest");
    setMinPrice(scalar(params.min_price_pkr) || "");
    setMaxPrice(scalar(params.max_price_pkr) || "");
    setMinSize(scalar(params.min_size_sqft) || "");
    setMaxSize(scalar(params.max_size_sqft) || "");
  }, [params]);

  // Derive quick budget preset selection based on transaction type (sale vs rent)
  const getBudgetPreset = () => {
    if (txType === "rent") {
      if (!minPrice && maxPrice === "100000") return "under-1l";
      if (minPrice === "100000" && maxPrice === "250000") return "1l-2.5l";
      if (minPrice === "250000" && maxPrice === "500000") return "2.5l-5l";
      if (minPrice === "500000" && maxPrice === "1000000") return "5l-10l";
      if (minPrice === "1000000" && !maxPrice) return "above-10l";
      if (!minPrice && !maxPrice) return "";
      return "custom";
    }
    // Sale presets
    if (!minPrice && maxPrice === "5000000") return "under-50l";
    if (minPrice === "5000000" && maxPrice === "15000000") return "50l-1.5cr";
    if (minPrice === "15000000" && maxPrice === "30000000") return "1.5cr-3cr";
    if (minPrice === "30000000" && maxPrice === "70000000") return "3cr-7cr";
    if (minPrice === "70000000" && maxPrice === "150000000") return "7cr-15cr";
    if (minPrice === "150000000" && !maxPrice) return "above-15cr";
    if (!minPrice && !maxPrice) return "";
    return "custom";
  };

  const handleBudgetPresetChange = (preset: string) => {
    let min = "";
    let max = "";
    if (txType === "rent") {
      if (preset === "under-1l") {
        max = "100000";
      } else if (preset === "1l-2.5l") {
        min = "100000";
        max = "250000";
      } else if (preset === "2.5l-5l") {
        min = "250000";
        max = "500000";
      } else if (preset === "5l-10l") {
        min = "500000";
        max = "1000000";
      } else if (preset === "above-10l") {
        min = "1000000";
      }
    } else {
      if (preset === "under-50l") {
        max = "5000000";
      } else if (preset === "50l-1.5cr") {
        min = "5000000";
        max = "15000000";
      } else if (preset === "1.5cr-3cr") {
        min = "15000000";
        max = "30000000";
      } else if (preset === "3cr-7cr") {
        min = "30000000";
        max = "70000000";
      } else if (preset === "7cr-15cr") {
        min = "70000000";
        max = "150000000";
      } else if (preset === "above-15cr") {
        min = "150000000";
      }
    }
    setMinPrice(min);
    setMaxPrice(max);
    applyFilters({
      min_price_pkr: min,
      max_price_pkr: max,
    });
  };

  const handleTxTypeChange = (newTx: string) => {
    setTxType(newTx);
    // Clear out of bounds budget presets when switching between rent and buy
    let resetPrice = false;
    const numMin = Number(minPrice);
    const numMax = Number(maxPrice);
    if (newTx === "rent" && (numMin >= 5000000 || numMax > 5000000)) {
      resetPrice = true;
    } else if (newTx === "sale" && numMax > 0 && numMax <= 1000000) {
      resetPrice = true;
    }

    if (resetPrice) {
      setMinPrice("");
      setMaxPrice("");
      applyFilters({ transaction_type: newTx, min_price_pkr: "", max_price_pkr: "" });
    } else {
      applyFilters({ transaction_type: newTx });
    }
  };

  const applyFilters = (overrides: Record<string, string> = {}) => {
    const nextParams = new URLSearchParams();

    // Carry forward existing parameters from URL so filters are preserved
    for (const [key, val] of Object.entries(params)) {
      const s = scalar(val).trim();
      if (s) nextParams.set(key, s);
    }

    const merged = {
      q,
      city,
      area,
      transaction_type: txType,
      property_type: propType,
      bedrooms,
      sort,
      min_price_pkr: minPrice,
      max_price_pkr: maxPrice,
      min_size_sqft: minSize,
      max_size_sqft: maxSize,
      ...overrides,
    };

    // Reset pagination to page 1 whenever filters or sorting change
    nextParams.delete("page");

    // Keep view parameter if present
    if (currentView && currentView !== "grid") {
      nextParams.set("view", currentView);
    }

    for (const [key, val] of Object.entries(merged)) {
      if (val !== undefined && val.trim()) {
        nextParams.set(key, val.trim());
      } else {
        nextParams.delete(key);
      }
    }

    startTransition(() => {
      router.push(`${pathname}?${nextParams.toString()}`);
    });
  };

  const handleQuickSector = (sector: string) => {
    setArea("");
    setQ(sector);
    applyFilters({ q: sector, area: "" });
  };

  const handleClearAll = () => {
    setQ("");
    setCity("");
    setArea("");
    setTxType("");
    setPropType("");
    setBedrooms("");
    setSort("newest");
    setMinPrice("");
    setMaxPrice("");
    setMinSize("");
    setMaxSize("");

    const next = currentView === "list" ? "?view=list" : "";
    startTransition(() => {
      router.push(`${pathname}${next}`);
    });
  };

  // Canonical sector presets across Islamabad & Rawalpindi
  const quickSectors = ["F-7", "DHA Phase 2", "Bahria Town", "Gulberg Greens", "F-10", "F-6", "E-11"];

  // Calculate active filter count
  const activeFilters: Array<{ key: string; label: string; onRemove: () => void }> = [];
  if (city) {
    activeFilters.push({
      key: "city",
      label: `City: ${city}`,
      onRemove: () => {
        setCity("");
        applyFilters({ city: "" });
      },
    });
  }
  if (area) {
    activeFilters.push({
      key: "area",
      label: `Area: ${area}`,
      onRemove: () => {
        setArea("");
        applyFilters({ area: "" });
      },
    });
  }
  if (txType) {
    activeFilters.push({
      key: "tx",
      label: `For ${txType === "sale" ? "Sale" : "Rent"}`,
      onRemove: () => {
        setTxType("");
        applyFilters({ transaction_type: "" });
      },
    });
  }
  if (propType) {
    activeFilters.push({
      key: "type",
      label: propType.charAt(0).toUpperCase() + propType.slice(1),
      onRemove: () => {
        setPropType("");
        applyFilters({ property_type: "" });
      },
    });
  }
  if (bedrooms) {
    activeFilters.push({
      key: "beds",
      label: `${bedrooms} Bed${bedrooms === "1" ? "" : "s"}`,
      onRemove: () => {
        setBedrooms("");
        applyFilters({ bedrooms: "" });
      },
    });
  }
  if (minPrice || maxPrice) {
    const preset = getBudgetPreset();
    let budgetLabel = "Custom Budget";
    if (txType === "rent") {
      if (preset === "under-1l") budgetLabel = "< 1 Lakh/mo";
      else if (preset === "1l-2.5l") budgetLabel = "1 - 2.5 Lakh/mo";
      else if (preset === "2.5l-5l") budgetLabel = "2.5 - 5 Lakh/mo";
      else if (preset === "5l-10l") budgetLabel = "5 - 10 Lakh/mo";
      else if (preset === "above-10l") budgetLabel = "> 10 Lakh/mo";
    } else {
      if (preset === "under-50l") budgetLabel = "< 50 Lac";
      else if (preset === "50l-1.5cr") budgetLabel = "50L - 1.5 Cr";
      else if (preset === "1.5cr-3cr") budgetLabel = "1.5 - 3 Cr";
      else if (preset === "3cr-7cr") budgetLabel = "3 - 7 Cr";
      else if (preset === "7cr-15cr") budgetLabel = "7 - 15 Cr";
      else if (preset === "above-15cr") budgetLabel = "> 15 Cr";
    }

    activeFilters.push({
      key: "price",
      label: budgetLabel,
      onRemove: () => {
        setMinPrice("");
        setMaxPrice("");
        applyFilters({ min_price_pkr: "", max_price_pkr: "" });
      },
    });
  }
  if (q) {
    activeFilters.push({
      key: "q",
      label: `"${q}"`,
      onRemove: () => {
        setQ("");
        applyFilters({ q: "" });
      },
    });
  }

  return (
    <div className={`filter-bar-container ${isPending ? "loading-state" : ""}`}>
      {/* Primary Sticky Pill Bar */}
      <div className="filter-pill-bar">
        {/* Transaction Type Segmented Toggle */}
        <div className="segmented-toggle">
          <button
            type="button"
            className={`toggle-option ${!txType ? "active" : ""}`}
            onClick={() => handleTxTypeChange("")}
          >
            All
          </button>
          <button
            type="button"
            className={`toggle-option ${txType === "sale" ? "active" : ""}`}
            onClick={() => handleTxTypeChange("sale")}
          >
            Buy
          </button>
          <button
            type="button"
            className={`toggle-option ${txType === "rent" ? "active" : ""}`}
            onClick={() => handleTxTypeChange("rent")}
          >
            Rent
          </button>
        </div>

        {/* Search Input Cell with Location Suggestions */}
        <div className="filter-search-box">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            list="location-filter-suggestions"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                applyFilters();
              }
            }}
            placeholder="Search sector, area, or keywords..."
            className="filter-text-input"
          />
          <datalist id="location-filter-suggestions">
            <option value="F-7" />
            <option value="DHA Phase 2" />
            <option value="Bahria Town Phase 7" />
            <option value="Gulberg Greens" />
            <option value="F-10" />
            <option value="F-6" />
            <option value="E-7" />
            <option value="E-11" />
            <option value="Blue Area" />
            <option value="G-13" />
          </datalist>
          {q && (
            <button
              type="button"
              className="clear-input-btn"
              onClick={() => {
                setQ("");
                applyFilters({ q: "" });
              }}
              title="Clear text"
            >
              ×
            </button>
          )}
        </div>

        {/* Property Type Dropdown */}
        <div className="filter-select-wrap">
          <select
            value={propType}
            onChange={(e) => {
              setPropType(e.target.value);
              applyFilters({ property_type: e.target.value });
            }}
            className="filter-pill-select"
            aria-label="Property type"
          >
            <option value="">All Property Types</option>
            <option value="house">House / Villa</option>
            <option value="apartment">Apartment / Flat</option>
            <option value="plot">Residential Plot</option>
            <option value="office">Commercial Office</option>
            <option value="shop">Retail Shop</option>
            <option value="warehouse">Warehouse</option>
          </select>
        </div>

        {/* Price Presets Dropdown */}
        <div className="filter-select-wrap">
          <select
            value={getBudgetPreset()}
            onChange={(e) => handleBudgetPresetChange(e.target.value)}
            className="filter-pill-select"
            aria-label="Price range"
          >
            <option value="">{txType === "rent" ? "Any Rent Budget" : "Any Budget"}</option>
            {txType === "rent" ? (
              <>
                <option value="under-1l">Under 1 Lakh / mo</option>
                <option value="1l-2.5l">1 - 2.5 Lakh / mo</option>
                <option value="2.5l-5l">2.5 - 5 Lakh / mo</option>
                <option value="5l-10l">5 - 10 Lakh / mo</option>
                <option value="above-10l">10+ Lakh / mo</option>
              </>
            ) : (
              <>
                <option value="under-50l">Under 50 Lakh</option>
                <option value="50l-1.5cr">50 Lakh - 1.5 Crore</option>
                <option value="1.5cr-3cr">1.5 - 3 Crore</option>
                <option value="3cr-7cr">3 - 7 Crore</option>
                <option value="7cr-15cr">7 - 15 Crore</option>
                <option value="above-15cr">15+ Crore</option>
              </>
            )}
            {getBudgetPreset() === "custom" && <option value="custom">Custom Range</option>}
          </select>
        </div>

        {/* Bedrooms Segmented Selector */}
        <div className="filter-select-wrap">
          <select
            value={bedrooms}
            onChange={(e) => {
              setBedrooms(e.target.value);
              applyFilters({ bedrooms: e.target.value });
            }}
            className="filter-pill-select"
            aria-label="Bedrooms"
          >
            <option value="">Any Beds</option>
            <option value="1">1 Bed</option>
            <option value="2">2 Beds</option>
            <option value="3">3 Beds</option>
            <option value="4">4 Beds</option>
            <option value="5">5+ Beds</option>
          </select>
        </div>

        {/* Advanced Filters Button */}
        <button
          type="button"
          className={`filter-btn-advanced ${showAdvanced ? "active" : ""}`}
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="4" y1="21" x2="4" y2="14" />
            <line x1="4" y1="10" x2="4" y2="3" />
            <line x1="12" y1="21" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12" y2="3" />
            <line x1="20" y1="21" x2="20" y2="16" />
            <line x1="20" y1="12" x2="20" y2="3" />
            <line x1="1" y1="14" x2="7" y2="14" />
            <line x1="9" y1="8" x2="15" y2="8" />
            <line x1="17" y1="16" x2="23" y2="16" />
          </svg>
          <span>More Filters</span>
        </button>

        {/* Search Action Button */}
        <button
          type="button"
          onClick={() => applyFilters()}
          className="filter-search-submit-btn"
        >
          Search
        </button>
      </div>

      {/* Advanced Filter Collapsible Drawer */}
      {showAdvanced && (
        <div className="filter-advanced-drawer">
          <div className="advanced-grid">
            <div>
              <label className="advanced-label">Custom Min Price (PKR)</label>
              <input
                type="number"
                placeholder="e.g. 10000000"
                value={minPrice}
                onChange={(e) => setMinPrice(e.target.value)}
                className="advanced-input"
              />
            </div>
            <div>
              <label className="advanced-label">Custom Max Price (PKR)</label>
              <input
                type="number"
                placeholder="e.g. 50000000"
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
                className="advanced-input"
              />
            </div>
            <div>
              <label className="advanced-label">Min Size (sq ft)</label>
              <input
                type="number"
                placeholder="e.g. 2250 (10 Marla)"
                value={minSize}
                onChange={(e) => setMinSize(e.target.value)}
                className="advanced-input"
              />
            </div>
            <div>
              <label className="advanced-label">Max Size (sq ft)</label>
              <input
                type="number"
                placeholder="e.g. 4500"
                value={maxSize}
                onChange={(e) => setMaxSize(e.target.value)}
                className="advanced-input"
              />
            </div>
          </div>
          <div className="advanced-actions">
            <button
              type="button"
              className="button small primary"
              onClick={() => {
                applyFilters();
                setShowAdvanced(false);
              }}
            >
              Apply Advanced Filters
            </button>
            <button
              type="button"
              className="button small secondary"
              onClick={() => setShowAdvanced(false)}
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Quick Sector Tags & Active Filter Strip */}
      <div className="filter-secondary-strip">
        <div className="quick-sectors-group">
          <span className="strip-title">Sectors:</span>
          {quickSectors.map((sector) => (
            <button
              key={sector}
              type="button"
              className={`sector-tag-btn ${q.toLowerCase() === sector.toLowerCase() ? "active" : ""}`}
              onClick={() => handleQuickSector(sector)}
            >
              {sector}
            </button>
          ))}
        </div>

        {/* Active Filter Badges */}
        {activeFilters.length > 0 && (
          <div className="active-filters-row">
            <span className="active-filters-label">Active:</span>
            {activeFilters.map((af) => (
              <span key={af.key} className="filter-chip-badge">
                {af.label}
                <button
                  type="button"
                  onClick={af.onRemove}
                  className="chip-remove-btn"
                  title="Remove filter"
                >
                  ×
                </button>
              </span>
            ))}
            <button
              type="button"
              onClick={handleClearAll}
              className="clear-all-filters-btn"
            >
              Clear All
            </button>
          </div>
        )}
      </div>

      {/* Control Bar: Total Count + Sort + Grid/List View Switcher */}
      <div className="results-control-bar">
        <div className="results-count-badge">
          <span className="count-number">{totalResults ?? 0}</span>
          <span className="count-label">
            {totalResults === 1 ? "Property Available" : "Properties Available"}
          </span>
          <span className="verified-guarantee-pill">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="3">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Direct Agency Inventory
          </span>
        </div>

        <div className="controls-right-group">
          {/* Sort By Dropdown */}
          <div className="sort-dropdown-wrap">
            <label htmlFor="sort-select" className="sort-label">Sort:</label>
            <select
              id="sort-select"
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                applyFilters({ sort: e.target.value });
              }}
              className="sort-select"
            >
              <option value="newest">Newest Listed</option>
              <option value="price_asc">Price: Low to High</option>
              <option value="price_desc">Price: High to Low</option>
              <option value="bedrooms_desc">Most Bedrooms</option>
              <option value="size_desc">Largest Size</option>
            </select>
          </div>

          {/* View Switcher: Grid vs List */}
          {onViewChange && (
            <div className="view-mode-switcher" role="group" aria-label="View layout">
              <button
                type="button"
                className={`view-btn ${currentView === "grid" ? "active" : ""}`}
                onClick={() => onViewChange("grid")}
                title="Grid view"
                aria-pressed={currentView === "grid"}
              >
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="7" height="7" rx="1" />
                  <rect x="14" y="3" width="7" height="7" rx="1" />
                  <rect x="14" y="14" width="7" height="7" rx="1" />
                  <rect x="3" y="14" width="7" height="7" rx="1" />
                </svg>
              </button>
              <button
                type="button"
                className={`view-btn ${currentView === "list" ? "active" : ""}`}
                onClick={() => onViewChange("list")}
                title="List view"
                aria-pressed={currentView === "list"}
              >
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="8" y1="6" x2="21" y2="6" />
                  <line x1="8" y1="12" x2="21" y2="12" />
                  <line x1="8" y1="18" x2="21" y2="18" />
                  <line x1="3" y1="6" x2="3.01" y2="6" strokeWidth="3" />
                  <line x1="3" y1="12" x2="3.01" y2="12" strokeWidth="3" />
                  <line x1="3" y1="18" x2="3.01" y2="18" strokeWidth="3" />
                </svg>
              </button>
              <button
                type="button"
                className={`view-btn ${currentView === "map" ? "active" : ""}`}
                onClick={() => onViewChange("map")}
                title="Sector Map view"
                aria-pressed={currentView === "map"}
              >
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
                  <line x1="8" y1="2" x2="8" y2="18" />
                  <line x1="16" y1="6" x2="16" y2="22" />
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
