export function canRequestVisit(property) {
  return property?.available === true;
}

export function availabilityLabel(available) {
  return available === true ? "Available" : "Unavailable";
}

export function inventorySourceLabel(source, version) {
  const cleanSource = typeof source === "string" ? source.trim() : "";
  const cleanVersion = typeof version === "string" ? version.trim() : "";
  const sourceLabel = cleanSource && cleanSource !== "unverified"
    ? `Inventory source: ${cleanSource}`
    : "Inventory source is unverified";
  return cleanVersion && cleanVersion !== "unspecified"
    ? `${sourceLabel} · ${cleanVersion}`
    : sourceLabel;
}

export function inventoryStatusSummary(loadState, properties) {
  if (loadState === "loading") {
    return { tone: "loading", label: "Loading listings", detail: "Retrieving property inventory" };
  }
  if (loadState === "error") {
    return { tone: "error", label: "Inventory offline", detail: "Property inventory could not be reached" };
  }
  if (properties.length === 0) {
    return { tone: "empty", label: "No listings loaded", detail: "No company properties have been imported" };
  }

  const availableCount = properties.filter(canRequestVisit).length;
  return {
    tone: "ready",
    label: `${availableCount} available · ${properties.length} total`,
    detail: `${properties.length} property ${properties.length === 1 ? "listing" : "listings"} loaded`,
  };
}

export function shouldAutoOpenInventoryImport(loadState, propertyCount) {
  return loadState === "ready" && propertyCount === 0;
}

/** Filter and sort the loaded company inventory without changing its source order. */
export function filterAndSortProperties(properties, filters = {}) {
  const city = normalizeFilter(filters.city);
  const area = normalizeFilter(filters.area);
  const purpose = normalizeFilter(filters.purpose);
  const direction = filters.sortOrder === "price_descending" ? -1 : 1;
  const maxPricePkr = Number.isFinite(filters.maxPricePkr) ? filters.maxPricePkr : null;
  const bedrooms = Number.isInteger(filters.bedrooms) ? filters.bedrooms : null;

  return properties
    .filter((property) =>
      (!city || normalizeFilter(property.city) === city)
      && (!area || normalizeFilter(property.area) === area)
      && (!purpose || normalizeFilter(property.purpose) === purpose)
      && (maxPricePkr === null || property.price_pkr <= maxPricePkr)
      && (bedrooms === null || property.bedrooms === bedrooms),
    )
    .map((property, index) => ({ property, index }))
    .sort((left, right) => {
      const priceDifference = (left.property.price_pkr - right.property.price_pkr) * direction;
      return priceDifference || left.index - right.index;
    })
    .map(({ property }) => property);
}

function normalizeFilter(value) {
  return typeof value === "string" ? value.trim().toLocaleLowerCase() : "";
}
