export type CivicCategory = "all" | "cda" | "gated" | "agro" | "commercial" | "waterfront";

export interface SectorDossierMeta {
  key: string;
  citySlug: string;
  areaSlug: string;
  city: string;
  area: string;
  title: string;
  authority: string;
  zone: string;
  category: CivicCategory;
  categoryLabel: string;
  img: string;
  priceRange: string;
  priceBenchmarkMarla: string;
  rentalYield: string;
  airportCommute: string;
  zeroPointCommute: string;
  lifestyle: string;
  description: string;
  nocStatus: string;
  keyHighlights: string[];
  activeListingCount: number;
}

export const SECTOR_METADATA_MAP: Record<string, SectorDossierMeta> = {
  "islamabad/dha-phase-2": {
    key: "islamabad/dha-phase-2",
    citySlug: "islamabad",
    areaSlug: "dha-phase-2",
    city: "Islamabad",
    area: "DHA Phase 2",
    title: "DHA Phase 2 & Giga Commercial Corridor",
    authority: "DHA Islamabad Validated",
    zone: "Defence Housing Authority · Zone V",
    category: "gated",
    categoryLabel: "Armed Forces Gated Enclave",
    img: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80",
    priceRange: "7.5 – 18 Cr PKR",
    priceBenchmarkMarla: "3.5 – 6.5 Cr / Kanal",
    rentalYield: "6.8% – 7.8% p.a.",
    airportCommute: "35 min",
    zeroPointCommute: "22 min",
    lifestyle: "Gated Security & WTC Mall",
    description: "Residential area with homes, leisure facilities, and retail around Giga Mall, with access to the Islamabad Expressway.",
    nocStatus: "DHA Statutory Ordinance Approved",
    keyHighlights: ["WTC Giga Mall", "Jacaranda Family Club", "Roots Ivy University", "Underground 11kV Grid", "24/7 Armed Patrols"],
    activeListingCount: 1,
  },
  "islamabad/f-7": {
    key: "islamabad/f-7",
    citySlug: "islamabad",
    areaSlug: "f-7",
    city: "Islamabad",
    area: "Sector F-7",
    title: "Sector F-7 & Jinnah Super Enclave",
    authority: "CDA Registered · Zone I",
    zone: "Capital Development Authority · Zone I",
    category: "cda",
    categoryLabel: "CDA Heritage & Diplomatic",
    img: "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=1200&q=80",
    priceRange: "14 – 35 Cr PKR",
    priceBenchmarkMarla: "12 – 18 Cr / Kanal",
    rentalYield: "7.5% – 9.0% p.a. (Foreign Diplomatic)",
    airportCommute: "30 min",
    zeroPointCommute: "7 min",
    lifestyle: "Diplomatic & Jinnah Super",
    description: "Established residential sector with leafy streets, embassy residences, and well-known shopping around Jinnah Super and Safa Gold Mall.",
    nocStatus: "Federal Capital Heritage Master Plan 1960",
    keyHighlights: ["Jinnah Super Markaz", "Safa Gold Mall", "Embassies & Foreign Missions", "Margalla Foothill Access", "Tree-Lined Avenues"],
    activeListingCount: 1,
  },
  "islamabad/f-10": {
    key: "islamabad/f-10",
    citySlug: "islamabad",
    areaSlug: "f-10",
    city: "Islamabad",
    area: "Sector F-10",
    title: "Sector F-10 & Margalla View Corridor",
    authority: "CDA Registered · Zone I",
    zone: "Capital Development Authority · Zone I",
    category: "cda",
    categoryLabel: "CDA Heritage & Diplomatic",
    img: "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1200&q=80",
    priceRange: "4 – 25 Cr PKR",
    priceBenchmarkMarla: "8 – 14 Cr / Kanal",
    rentalYield: "6.5% – 7.8% p.a.",
    airportCommute: "28 min",
    zeroPointCommute: "10 min",
    lifestyle: "Margalla Views & F-9 Park",
    description: "Residential sector near Fatima Jinnah Park, with neighborhood shopping and a mix of housing options.",
    nocStatus: "Federal Capital Heritage Master Plan 1960",
    keyHighlights: ["Bordering Fatima Jinnah (F-9) Park", "F-10 Commercial Markaz", "Silver Oaks Executive Residences", "International Banking Hub", "Margalla Vistas"],
    activeListingCount: 1,
  },
  "islamabad/gulberg-greens": {
    key: "islamabad/gulberg-greens",
    citySlug: "islamabad",
    areaSlug: "gulberg-greens",
    city: "Islamabad",
    area: "Gulberg Greens",
    title: "Gulberg Greens Agro Farmhouses",
    authority: "IBECHS / CDA NOC Approved",
    zone: "Islamabad Master Plan · Zone IV",
    category: "agro",
    categoryLabel: "Agro-Farmhouse Estates",
    img: "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1200&q=80",
    priceRange: "12 – 30 Cr PKR",
    priceBenchmarkMarla: "3.0 – 5.5 Cr / Kanal",
    rentalYield: "5.5% – 7.0% p.a.",
    airportCommute: "30 min",
    zeroPointCommute: "15 min",
    lifestyle: "Agro Farmhouse Living",
    description: "A lower-density, farmhouse-oriented part of Islamabad with larger residential plots and a quieter suburban feel.",
    nocStatus: "CDA NOC # CDA/PLW/RP-Agro/95",
    keyHighlights: ["4 to 10+ Kanal Parcels", "220-ft Wide Boulevards", "Dedicated Solar Grids", "Private Orchards & Stables", "Underground Electricity"],
    activeListingCount: 1,
  },
  "rawalpindi/bahria-town-phase-7": {
    key: "rawalpindi/bahria-town-phase-7",
    citySlug: "rawalpindi",
    areaSlug: "bahria-town-phase-7",
    city: "Rawalpindi",
    area: "Bahria Town Phase 7",
    title: "Bahria Town Phase 7 River Promenade",
    authority: "Bahria Town / RDA Registered",
    zone: "Rawalpindi Development Authority (RDA)",
    category: "waterfront",
    categoryLabel: "Waterfront Promenade & High-Rises",
    img: "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&w=1200&q=80",
    priceRange: "3.5 – 9 Cr PKR",
    priceBenchmarkMarla: "1.8 – 3.2 Cr / Kanal",
    rentalYield: "8.0% – 9.5% p.a.",
    airportCommute: "40 min",
    zeroPointCommute: "25 min",
    lifestyle: "River Promenade & High-Rises",
    description: "A planned residential area in Rawalpindi with shopping, healthcare, and leisure destinations around Bahria Town.",
    nocStatus: "RDA Approved Layout Plan",
    keyHighlights: ["Soan River Promenade Dining", "Green Valley Hypermarket", "Bahria International Hospital", "Uninterrupted Independent Power", "Championship Golf Access"],
    activeListingCount: 1,
  },
  "islamabad/blue-area": {
    key: "islamabad/blue-area",
    citySlug: "islamabad",
    areaSlug: "blue-area",
    city: "Islamabad",
    area: "Blue Area",
    title: "Blue Area Financial & Corporate Boulevard",
    authority: "CDA Commercial · Jinnah Avenue",
    zone: "CDA Central Business District · Zone I",
    category: "commercial",
    categoryLabel: "Corporate Financial District",
    img: "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&q=80",
    priceRange: "8 – 50+ Cr PKR",
    priceBenchmarkMarla: "25 – 45 Cr / Commercial Plot",
    rentalYield: "8.5% – 11.2% p.a. (Grade-A Office)",
    airportCommute: "28 min",
    zeroPointCommute: "3 min",
    lifestyle: "Corporate & Metro Transit",
    description: "Islamabad's main commercial corridor along Jinnah Avenue, with offices, retail, and public transport connections.",
    nocStatus: "CDA Commercial By-Laws 2020 Compliant",
    keyHighlights: ["Pakistan Stock Exchange (PSX)", "Jinnah Avenue Frontage", "Direct Metro Bus Stations", "Grade-A High-Rise Floorplates", "Federal Ministry Proximity"],
    activeListingCount: 1,
  },
};

export const CIVIC_CATEGORIES = [
  { id: "all", label: "All Sectors" },
  { id: "cda", label: "CDA Heritage (F-7, F-10)" },
  { id: "gated", label: "Armed Forces Enclaves (DHA)" },
  { id: "commercial", label: "Financial CBD (Blue Area)" },
  { id: "agro", label: "Agro Farmhouses (Gulberg)" },
  { id: "waterfront", label: "River Promenade (Bahria)" },
] as const;

export const CIVIC_TRUST_PILLARS = [
  {
    title: "Municipal & Civic Zoning",
    code: "CDA / DHA / RDA Compliance",
    description: "Every sector is cross-indexed against the Federal Capital Master Plan 1960, DHA Ordinance, and RDA Master Framework with statutory boundary demarcation.",
    badge: "Master Plan Audited",
  },
  {
    title: "Title & Transfer Non-Encumbrance",
    code: "NDC & Mutation Verification",
    description: "Guaranteed No Demand Certificate (NDC) clearance, allotment ledger integrity, and biometric transfer protocols through official Directorate One-Window desks.",
    badge: "Zero Title Cloud",
  },
  {
    title: "Infrastructure & Grid Autonomy",
    code: "11kV Grids & Standby Utilities",
    description: "Underground electrical routing, dedicated grid substations, fiber optic backbones, and deep aquifer water supply networks validated on-site.",
    badge: "Continuous Power",
  },
  {
    title: "FBR Tax & Statutory Compliance",
    code: "Sections 236C, 236K & 7E",
    description: "Transparent withholding tax guidance for filers vs non-filers, capital value tax audits, and exemption certificates under Finance Act regulations.",
    badge: "FBR Certified",
  },
];

export function getSectorMetadata(citySlug: string, areaSlug: string): SectorDossierMeta {
  const normCity = citySlug.toLowerCase().replace(/[\s_]+/g, "-");
  const normArea = areaSlug.toLowerCase().replace(/[\s_]+/g, "-");
  const key = `${normCity}/${normArea}`;

  if (SECTOR_METADATA_MAP[key]) {
    return SECTOR_METADATA_MAP[key];
  }

  // Fallback match by partial area slug
  for (const [mapKey, meta] of Object.entries(SECTOR_METADATA_MAP)) {
    if (mapKey.includes(normArea) || normArea.includes(meta.areaSlug)) {
      return meta;
    }
  }

  // Generic fallback
  return {
    key,
    citySlug: normCity,
    areaSlug: normArea,
    city: citySlug.charAt(0).toUpperCase() + citySlug.slice(1),
    area: areaSlug.replace(/-/g, " ").toUpperCase(),
    title: `${areaSlug.replace(/-/g, " ").toUpperCase()} Sector Dossier`,
    authority: "Not specified",
    zone: "Area information not provided",
    category: "cda",
    categoryLabel: "Urban Residential",
    img: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80",
    priceRange: "Not available",
    priceBenchmarkMarla: "Not available",
    rentalYield: "Not available",
    airportCommute: "Not available",
    zeroPointCommute: "Not available",
    lifestyle: "Area guide",
    description: "Area details are being prepared. Browse published listings to see properties available in this location.",
    nocStatus: "Not provided",
    keyHighlights: [],
    activeListingCount: 0,
  };
}
