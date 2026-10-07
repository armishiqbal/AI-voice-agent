import Link from "next/link";

interface NeighborhoodData {
  city: string;
  area: string;
  name: string;
  subtitle: string;
  avgPrice: string;
  badge: string;
  imageUrl: string;
  landmarks: string[];
}

const neighborhoods: NeighborhoodData[] = [
  {
    city: "Islamabad",
    area: "F-7",
    name: "Sector F-7 & Diplomatic Core",
    subtitle: "The capital's premier residential sector with Margalla Hills vistas and upscale dining.",
    avgPrice: "PKR 9.5 Cr – 24 Cr",
    badge: "Ultra-Luxury Living",
    imageUrl: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80",
    landmarks: ["Margalla National Park", "F-6 Super Market", "Islamabad Club"],
  },
  {
    city: "Islamabad",
    area: "DHA Phase 2",
    name: "DHA Islamabad Phase 2",
    subtitle: "Master-planned gated security, top-tier international academies, and wide landscaped boulevards.",
    avgPrice: "PKR 3.5 Cr – 9.8 Cr",
    badge: "Gated Community",
    imageUrl: "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=800&q=80",
    landmarks: ["Giga Mall Commercial", "DHA Club", "Roots Ivy World Campus"],
  },
  {
    city: "Rawalpindi",
    area: "Bahria Town Phase 7",
    name: "Bahria Town Phase 7",
    subtitle: "Fully self-sustained infrastructure, civic amenities, and thriving commercial hubs.",
    avgPrice: "PKR 2.6 Cr – 8.2 Cr",
    badge: "Master-Planned Community",
    imageUrl: "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=800&q=80",
    landmarks: ["River View Commercial", "Safari Club", "Greenvalley Supermarket"],
  },
  {
    city: "Islamabad",
    area: "Gulberg Greens",
    name: "Gulberg Greens & Expressway",
    subtitle: "Picturesque 4–10 Kanal agro-farmhouses and rapid direct access to the new Islamabad International Airport.",
    avgPrice: "PKR 4.8 Cr – 16 Cr",
    badge: "Agro-Farmhouses",
    imageUrl: "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=800&q=80",
    landmarks: ["Gulberg Expressway", "Karakoram Enclave", "New Airport Link"],
  },
];

export function NeighborhoodExplorer() {
  return (
    <div className="neighborhood-luxury-grid">
      {neighborhoods.map((item) => (
        <Link
          key={`${item.city}-${item.area}`}
          href={`/properties?city=${encodeURIComponent(item.city)}&area=${encodeURIComponent(item.area)}`}
          className="neighborhood-card-luxury"
        >
          {/* Architectural Background Photography */}
          <div
            className="neighborhood-bg-image"
            style={{ backgroundImage: `url(${item.imageUrl})` }}
            role="img"
            aria-label={item.name}
          />
          <div className="neighborhood-gradient-overlay" />

          {/* Card Badges Strip */}
          <div className="card-top-badges">
            <span className="card-badge-tag">{item.badge}</span>
            <span className="card-badge-verified">Verified Sector</span>
          </div>

          {/* Card Content & Details */}
          <div className="neighborhood-card-content">
            <span className="neighborhood-city-label">
              {item.city === "Islamabad" ? "Islamabad Capital Territory" : "Rawalpindi Metro"}
            </span>

            <h3 className="neighborhood-card-title">{item.name}</h3>

            <p className="neighborhood-card-sub">{item.subtitle}</p>

            {/* Landmarks chips */}
            <div className="neighborhood-landmarks-row">
              {item.landmarks.map((landmark) => (
                <span key={landmark} className="landmark-chip">
                  • {landmark}
                </span>
              ))}
            </div>

            <div className="neighborhood-card-footer">
              <div>
                <span className="price-range-label">Average Range</span>
                <p className="price-range-val">{item.avgPrice}</p>
              </div>

              <span className="explore-action-pill">
                Explore Homes &rarr;
              </span>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
