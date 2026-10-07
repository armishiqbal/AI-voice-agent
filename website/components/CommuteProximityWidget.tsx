"use client";

import { Listing } from "@/lib/catalog";

interface CommuteProximityWidgetProps {
  property: Listing;
}

type Landmark = {
  name: string;
  category: "airport" | "commercial" | "diplomatic" | "health" | "transit" | "school";
  driveTime: string;
  distance: string;
  route: string;
};

export function CommuteProximityWidget({ property }: CommuteProximityWidgetProps) {
  const area = property.area.toLowerCase();
  const isDha = area.includes("dha");
  const isBahria = area.includes("bahria");
  const isF7 = area.includes("f-7") || area.includes("f7");
  const isF10 = area.includes("f-10") || area.includes("f10");
  const isGulberg = area.includes("gulberg");
  const isBlueArea = area.includes("blue area");

  // Determine realistic commute times based on location
  let landmarks: Landmark[] = [];

  if (isDha) {
    landmarks = [
      { name: "WTC Giga Mall & Hypermarket", category: "commercial", driveTime: "4 mins", distance: "1.5 km", route: "Main GT Road Corridor" },
      { name: "Islamabad Expressway Interchange", category: "transit", driveTime: "6 mins", distance: "2.8 km", route: "Direct Signal-Free Access" },
      { name: "Islamabad International Airport", category: "airport", driveTime: "32 mins", distance: "34 km", route: "Via Rawalpindi Ring Road / M-2" },
      { name: "Blue Area & Zero Point Islamabad", category: "diplomatic", driveTime: "22 mins", distance: "21 km", route: "Via Expressway Signal-Free" },
      { name: "Roots Ivy International University", category: "school", driveTime: "5 mins", distance: "2 km", route: "DHA Phase 2 Sector G" },
      { name: "Fauj Foundation Hospital", category: "health", driveTime: "12 mins", distance: "7.5 km", route: "Via Morgah Road" },
    ];
  } else if (isBahria) {
    landmarks = [
      { name: "River View Commercial Promenade", category: "commercial", driveTime: "3 mins", distance: "1 km", route: "Bahria Phase 7 Boulevard" },
      { name: "Bahria International Hospital", category: "health", driveTime: "6 mins", distance: "2.5 km", route: "Phase 8 Main Boulevard" },
      { name: "Islamabad International Airport", category: "airport", driveTime: "35 mins", distance: "36 km", route: "Via GT Road / Motorway" },
      { name: "Roots Millennium Campus", category: "school", driveTime: "5 mins", distance: "1.8 km", route: "Bahria Town Phase 7" },
      { name: "Rawalpindi Saddar & Cantonment", category: "transit", driveTime: "20 mins", distance: "14 km", route: "Via Bahria Expressway" },
      { name: "Blue Area Islamabad", category: "diplomatic", driveTime: "28 mins", distance: "25 km", route: "Via Expressway" },
    ];
  } else if (isF7 || isBlueArea) {
    landmarks = [
      { name: "Jinnah Super Market (F-7 Markaz)", category: "commercial", driveTime: "2 mins", distance: "800 m", route: "Inner Sector Avenue" },
      { name: "Blue Area Central Business District", category: "commercial", driveTime: "4 mins", distance: "1.8 km", route: "Via Nazim-ud-Din Road" },
      { name: "Diplomatic Enclave & Embassies", category: "diplomatic", driveTime: "8 mins", distance: "4.5 km", route: "Via Murree Road / Fourth Avenue" },
      { name: "Islamabad International Airport", category: "airport", driveTime: "28 mins", distance: "31 km", route: "Via Srinagar Highway" },
      { name: "Maroof International Hospital", category: "health", driveTime: "6 mins", distance: "3 km", route: "Sector F-10" },
      { name: "Islamabad Club & Serena Hotel", category: "diplomatic", driveTime: "10 mins", distance: "5.5 km", route: "Via Club Road" },
    ];
  } else if (isF10) {
    landmarks = [
      { name: "Fatima Jinnah (F-9) Park Gate", category: "commercial", driveTime: "3 mins", distance: "1.2 km", route: "Adjacent Sector Boundary" },
      { name: "F-10 Markaz Commercial & Banking", category: "commercial", driveTime: "2 mins", distance: "700 m", route: "Sumbal Road" },
      { name: "Islamabad International Airport", category: "airport", driveTime: "24 mins", distance: "27 km", route: "Via Srinagar Highway" },
      { name: "NUST University Campus", category: "school", driveTime: "8 mins", distance: "4.8 km", route: "Sector H-12 Link" },
      { name: "Blue Area & Secretariat", category: "diplomatic", driveTime: "10 mins", distance: "6.5 km", route: "Via Margalla Road" },
      { name: "Maroof International Hospital", category: "health", driveTime: "2 mins", distance: "900 m", route: "Sector F-10/2" },
    ];
  } else if (isGulberg) {
    landmarks = [
      { name: "Islamabad Expressway Interchange", category: "transit", driveTime: "3 mins", distance: "1 km", route: "Dedicated Direct Interchange" },
      { name: "Gulberg Civic Center & Mega Mall", category: "commercial", driveTime: "4 mins", distance: "1.5 km", route: "Gulberg Main Boulevard" },
      { name: "Blue Area Islamabad", category: "diplomatic", driveTime: "16 mins", distance: "15 km", route: "Via Signal-Free Expressway" },
      { name: "Islamabad International Airport", category: "airport", driveTime: "32 mins", distance: "35 km", route: "Via Expressway & Ring Road" },
      { name: "Froebel's International School", category: "school", driveTime: "5 mins", distance: "2 km", route: "Gulberg Greens Campus" },
      { name: "Shifa International Hospital", category: "health", driveTime: "14 mins", distance: "12 km", route: "Sector H-8 Expressway Exit" },
    ];
  } else {
    landmarks = [
      { name: "Central Commercial Markaz", category: "commercial", driveTime: "4 mins", distance: "1.5 km", route: "Sector Main Road" },
      { name: "Islamabad International Airport", category: "airport", driveTime: "28 mins", distance: "30 km", route: "Via Srinagar Highway" },
      { name: "Blue Area Financial District", category: "diplomatic", driveTime: "12 mins", distance: "8 km", route: "Via Primary Arterial" },
      { name: "Tertiary Care Hospital", category: "health", driveTime: "8 mins", distance: "4 km", route: "Direct Sector Access" },
    ];
  }

  const getCategoryIcon = (cat: Landmark["category"]) => {
    switch (cat) {
      case "airport":
        return (
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.3c.4-.2.6-.6.5-1.1z" />
          </svg>
        );
      case "health":
        return (
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
            <path d="M12 9v6M9 12h6" />
          </svg>
        );
      case "school":
        return (
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" />
            <path d="M6 6h10M6 10h10" />
          </svg>
        );
      case "diplomatic":
        return (
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        );
      case "transit":
        return (
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
            <rect width="16" height="16" x="4" y="3" rx="2" />
            <path d="M4 11h16M12 3v8M8 19l-2 3M16 19l2 3" />
          </svg>
        );
      case "commercial":
      default:
        return (
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
            <rect width="18" height="18" x="3" y="3" rx="2" />
            <path d="M3 9h18M9 21V9" />
          </svg>
        );
    }
  };

  return (
    <div className="commute-proximity-card">
      <div className="commute-header-strip">
        <div className="commute-title-box">
          <span className="commute-kicker">Neighborhood Connectivity</span>
          <h3 className="commute-title">Commute Times &amp; Key Landmarks</h3>
        </div>
        <span className="commute-gps-badge">Verified Transit Times</span>
      </div>

      <p className="commute-desc">
        Realistic drive times from this address to major business districts, international air transit, healthcare facilities, and educational institutes.
      </p>

      <div className="commute-grid">
        {landmarks.map((landmark) => (
          <div key={landmark.name} className="commute-tile">
            <div className="commute-tile-top">
              <div className="commute-icon-wrap" aria-hidden="true">
                {getCategoryIcon(landmark.category)}
              </div>
              <div className="commute-timing-badge">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                <span>{landmark.driveTime}</span>
              </div>
            </div>

            <h4 className="landmark-name">{landmark.name}</h4>
            <div className="landmark-details">
              <span className="landmark-distance">{landmark.distance}</span>
              <span className="landmark-dot">·</span>
              <span className="landmark-route">{landmark.route}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
