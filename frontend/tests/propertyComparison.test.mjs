import assert from "node:assert/strict";
import test from "node:test";
import { availabilityLabel, canRequestVisit, filterAndSortProperties, inventorySourceLabel, inventoryStatusSummary, shouldAutoOpenInventoryImport } from "../src/propertyFacts.mjs";

function formatPricePKR(price) {
  if (price >= 10_000_000) {
    const crore = (price / 10_000_000).toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
    return `PKR ${crore} Crore`;
  }
  if (price >= 100_000) {
    const lakh = (price / 100_000).toFixed(1).replace(/\.0$/, "");
    return `PKR ${lakh} Lakh`;
  }
  return `PKR ${price.toLocaleString()}`;
}

function getMarlaEquivalent(sqft) {
  if (sqft >= 4500) {
    const kanal = (sqft / 4500).toFixed(1).replace(/\.0$/, "");
    return `${kanal} Kanal`;
  }
  const marla = (sqft / 225).toFixed(1).replace(/\.0$/, "");
  return `${marla} Marla`;
}

test("formatPricePKR formats Crore, Lakh, and standard amounts accurately", () => {
  assert.equal(formatPricePKR(45_000_000), "PKR 4.5 Crore");
  assert.equal(formatPricePKR(10_000_000), "PKR 1 Crore");
  assert.equal(formatPricePKR(250_000), "PKR 2.5 Lakh");
  assert.equal(formatPricePKR(85_000), "PKR 85,000");
});

test("getMarlaEquivalent converts square feet to Pakistani land units", () => {
  assert.equal(getMarlaEquivalent(225), "1 Marla");
  assert.equal(getMarlaEquivalent(1125), "5 Marla");
  assert.equal(getMarlaEquivalent(2250), "10 Marla");
  assert.equal(getMarlaEquivalent(4500), "1 Kanal");
  assert.equal(getMarlaEquivalent(9000), "2 Kanal");
});

test("visit requests require loaded available inventory", () => {
  assert.equal(canRequestVisit({ available: true }), true);
  assert.equal(canRequestVisit({ available: false }), false);
  assert.equal(canRequestVisit(undefined), false);
  assert.equal(availabilityLabel(true), "Available");
  assert.equal(availabilityLabel(false), "Unavailable");
});

test("inventory source labels never imply verification when source is missing", () => {
  assert.equal(inventorySourceLabel("unverified", "unspecified"), "Inventory source is unverified");
  assert.equal(inventorySourceLabel("client-inventory-2026-09", "rev-2"), "Inventory source: client-inventory-2026-09 · rev-2");
});

test("inventory status summarizes loading, unavailable, empty, and loaded inventory honestly", () => {
  assert.deepEqual(inventoryStatusSummary("loading", []), {
    tone: "loading", label: "Loading listings", detail: "Retrieving property inventory",
  });
  assert.equal(inventoryStatusSummary("error", []).label, "Inventory offline");
  assert.equal(inventoryStatusSummary("ready", []).label, "No listings loaded");
  assert.deepEqual(inventoryStatusSummary("ready", [
    { available: true }, { available: false }, { available: true },
  ]), {
    tone: "ready", label: "2 available · 3 total", detail: "3 property listings loaded",
  });
});

test("inventory import expands only after a successful empty live inventory response", () => {
  assert.equal(shouldAutoOpenInventoryImport("loading", 0), false);
  assert.equal(shouldAutoOpenInventoryImport("error", 0), false);
  assert.equal(shouldAutoOpenInventoryImport("ready", 0), true);
  assert.equal(shouldAutoOpenInventoryImport("ready", 2), false);
});

test("inventory browsing filters by normalized purpose and location, then sorts by price", () => {
  const listings = [
    { id: "rental", city: "Karachi", area: "DHA", purpose: "rent", bedrooms: 2, price_pkr: 2_000_000 },
    { id: "sale", city: "Karachi", area: "DHA", purpose: "sale", bedrooms: 3, price_pkr: 12_000_000 },
    { id: "cheap-rental", city: "Karachi", area: "Clifton", purpose: "rent", bedrooms: 1, price_pkr: 1_000_000 },
    { id: "lahore", city: "Lahore", area: "DHA", purpose: "rent", bedrooms: 2, price_pkr: 500_000 },
  ];

  assert.deepEqual(filterAndSortProperties(listings, {
    city: " KARACHI ", area: "dha", purpose: "RENT", sortOrder: "price_ascending",
  }).map(({ id }) => id), ["rental"]);
  assert.deepEqual(filterAndSortProperties(listings, {
    purpose: "rent", sortOrder: "price_descending",
  }).map(({ id }) => id), ["rental", "cheap-rental", "lahore"]);
});

test("inventory price sorting is stable for ties and never mutates live records", () => {
  const listings = [
    { id: "first", city: "Karachi", area: "DHA", purpose: "sale", bedrooms: 2, price_pkr: 5_000_000 },
    { id: "second", city: "Karachi", area: "DHA", purpose: "sale", bedrooms: 2, price_pkr: 5_000_000 },
    { id: "third", city: "Karachi", area: "DHA", purpose: "sale", bedrooms: 2, price_pkr: 1_000_000 },
  ];
  const originalOrder = listings.map(({ id }) => id);

  assert.deepEqual(filterAndSortProperties(listings).map(({ id }) => id), ["third", "first", "second"]);
  assert.deepEqual(listings.map(({ id }) => id), originalOrder);
});

test("inventory browsing applies maximum PKR price and exact bedroom filters", () => {
  const listings = [
    { id: "within-budget", city: "Karachi", area: "DHA", purpose: "sale", bedrooms: 2, price_pkr: 30_000_000 },
    { id: "over-budget", city: "Karachi", area: "DHA", purpose: "sale", bedrooms: 2, price_pkr: 60_000_000 },
    { id: "wrong-bedroom-count", city: "Karachi", area: "DHA", purpose: "sale", bedrooms: 3, price_pkr: 25_000_000 },
  ];

  assert.deepEqual(filterAndSortProperties(listings, {
    maxPricePkr: 50_000_000, bedrooms: 2,
  }).map(({ id }) => id), ["within-budget"]);
  assert.deepEqual(filterAndSortProperties(listings, {
    maxPricePkr: Number.NaN, bedrooms: 2,
  }).map(({ id }) => id), ["within-budget", "over-budget"]);
});
