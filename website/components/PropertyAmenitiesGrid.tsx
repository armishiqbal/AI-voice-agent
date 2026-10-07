import React from "react";

interface PropertyAmenitiesGridProps {
  amenities: string[];
}

interface AmenityMeta {
  label: string;
  icon: React.ReactNode;
}

export function PropertyAmenitiesGrid({ amenities }: PropertyAmenitiesGridProps) {
  if (!amenities || amenities.length === 0) {
    return (
      <div className="amenities-empty">
        <p>Specific amenities have not been cataloged for this listing. Contact our staff for detailed equipment and utility specifications.</p>
      </div>
    );
  }

  const getAmenityMeta = (raw: string): AmenityMeta => {
    const text = raw.toLowerCase().trim();

    // Parking / Garage
    if (text.includes("parking") || text.includes("garage") || text.includes("car porch") || text.includes("car")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="5" width="20" height="14" rx="2" />
            <path d="M9 16V8h4a2 2 0 0 1 0 4H9" />
          </svg>
        ),
      };
    }

    // Power / Generator / Solar
    if (text.includes("generator") || text.includes("solar") || text.includes("ups") || text.includes("electricity") || text.includes("power")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        ),
      };
    }

    // Security / Gated / Guard / CCTV
    if (text.includes("security") || text.includes("guard") || text.includes("cctv") || text.includes("gated")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        ),
      };
    }

    // Garden / Lawn / Green
    if (text.includes("garden") || text.includes("lawn") || text.includes("terrace") || text.includes("balcony")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 19V6M8 11l4-4 4 4M5 19h14" />
            <path d="M12 3a6 6 0 0 0-6 6c0 3 2 5 6 10 4-5 6-7 6-10a6 6 0 0 0-6-6z" />
          </svg>
        ),
      };
    }

    // Pool / Swimming
    if (text.includes("pool") || text.includes("swimming") || text.includes("jacuzzi")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 12h20M2 16c2 1 4 1 6 0s4-1 6 0 4 1 6 0M2 20c2 1 4 1 6 0s4-1 6 0 4 1 6 0" />
            <circle cx="12" cy="7" r="3" />
          </svg>
        ),
      };
    }

    // Air conditioning / Heating / HVAC
    if (text.includes("ac") || text.includes("air") || text.includes("heating") || text.includes("climate") || text.includes("cooling")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2v20M2 12h20M4.93 4.93l14.14 14.14M4.93 19.07l14.14-14.14" />
          </svg>
        ),
      };
    }

    // Water / Boring / Filtration
    if (text.includes("water") || text.includes("boring") || text.includes("filter") || text.includes("tank")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
          </svg>
        ),
      };
    }

    // Gym / Fitness
    if (text.includes("gym") || text.includes("fitness") || text.includes("workout")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 5v14M18 5v14M3 9v6M21 9v6M6 12h12" />
          </svg>
        ),
      };
    }

    // Kitchen / Appliances / Pantry
    if (text.includes("kitchen") || text.includes("pantry") || text.includes("appliance")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2" />
            <path d="M7 2v20" />
            <path d="M21 15V2v0a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7" />
          </svg>
        ),
      };
    }

    // Internet / Fiber / Smart
    if (text.includes("internet") || text.includes("wifi") || text.includes("fiber") || text.includes("smart")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 12.55a11 11 0 0 1 14.08 0" />
            <path d="M1.42 9a16 16 0 0 1 21.16 0" />
            <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
            <line x1="12" y1="20" x2="12.01" y2="20" strokeWidth="3" />
          </svg>
        ),
      };
    }

    // Elevator / Lift
    if (text.includes("elevator") || text.includes("lift")) {
      return {
        label: raw,
        icon: (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <polyline points="7 10 10 7 13 10" />
            <polyline points="17 14 14 17 11 14" />
          </svg>
        ),
      };
    }

    // Default luxury feature chip
    return {
      label: raw,
      icon: (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ),
    };
  };

  return (
    <div className="amenities-grid-luxury">
      {amenities.map((item, index) => {
        const meta = getAmenityMeta(item);
        return (
          <div key={`${item}-${index}`} className="amenity-chip-luxury">
            <div className="amenity-icon-box">{meta.icon}</div>
            <span className="amenity-label">{meta.label}</span>
          </div>
        );
      })}
    </div>
  );
}
