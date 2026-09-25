import assert from "node:assert/strict";
import test from "node:test";

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

function getNocStatus(area) {
  const a = area.toLowerCase();
  if (a.includes("clifton")) return { status: "SBCA APPROVED", authority: "Sindh Building Control Authority" };
  if (a.includes("dha")) return { status: "DHA APPROVED", authority: "Defence Housing Authority / Cantonment" };
  if (a.includes("gulberg")) return { status: "LDA APPROVED", authority: "Lahore Development Authority" };
  if (a.includes("blue area") || a.includes("f-11")) return { status: "CDA APPROVED", authority: "Capital Development Authority" };
  return { status: "VERIFIED CLEAR TITLE", authority: "Local Land Registry & Town Planning" };
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

test("getNocStatus verifies regulatory authorities by Pakistani locality", () => {
  assert.equal(getNocStatus("Clifton Block 4").status, "SBCA APPROVED");
  assert.equal(getNocStatus("DHA Phase 6").status, "DHA APPROVED");
  assert.equal(getNocStatus("Gulberg III").status, "LDA APPROVED");
  assert.equal(getNocStatus("Blue Area").status, "CDA APPROVED");
  assert.equal(getNocStatus("Bahria Town").status, "VERIFIED CLEAR TITLE");
});
