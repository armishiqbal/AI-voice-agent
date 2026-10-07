"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { Agency, Agent } from "@/lib/marketplace";

type AgentsDirectoryExplorerProps = {
  agencies: Agency[];
  agents: Agent[];
};

const SECTORS = [
  "All areas",
  "Islamabad",
  "Rawalpindi",
  "DHA Phase 2",
  "Blue Area",
  "Gulberg Greens",
  "Sector F-6 / F-7 / F-8",
  "Bahria Town",
];

export function AgentsDirectoryExplorer({
  agencies,
  agents,
}: AgentsDirectoryExplorerProps) {
  const [search, setSearch] = useState("");
  const [selectedSector, setSelectedSector] = useState("All areas");
  const [activeTab, setActiveTab] = useState<"all" | "agencies" | "agents">("all");

  const cleanPhone = (phone?: string | null) => {
    if (!phone) return "";
    return phone.replace(/[^0-9]/g, "");
  };

  const matchesSector = (coverage: string[], specialties?: string[]) => {
    if (selectedSector === "All areas") return true;

    const query = selectedSector.toLowerCase();
    const sectorHaystack = [
      ...coverage,
      ...(specialties || []),
    ].map((s) => s.toLowerCase());

    if (query.includes("f-6 / f-7 / f-8")) {
      return sectorHaystack.some(
        (s) =>
          s.includes("f-6") ||
          s.includes("f-7") ||
          s.includes("f-8") ||
          s.includes("diplomatic")
      );
    }

    if (query === "islamabad") {
      return sectorHaystack.some((s) => s.includes("islamabad"));
    }

    if (query === "rawalpindi") {
      return sectorHaystack.some((s) => s.includes("rawalpindi") || s.includes("bahria"));
    }

    if (query.includes("bahria town")) {
      return sectorHaystack.some(
        (s) => s.includes("bahria") || s.includes("rawalpindi")
      );
    }

    return sectorHaystack.some(
      (s) => s.includes(query) || query.includes(s)
    );
  };

  const filteredAgencies = useMemo(() => {
    const q = search.trim().toLowerCase();
    return agencies.filter((org) => {
      const sectorOk = matchesSector(org.coverage);
      if (!sectorOk) return false;

      if (!q) return true;
      const haystack = [
        org.name,
        org.description,
        org.address || "",
        org.license_number || "",
        ...org.coverage,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [agencies, search, selectedSector]);

  const filteredAgents = useMemo(() => {
    const q = search.trim().toLowerCase();
    return agents.filter((person) => {
      const sectorOk = matchesSector(
        person.agency.coverage,
        person.specialties
      );
      if (!sectorOk) return false;

      if (!q) return true;
      const haystack = [
        person.name,
        person.title || "",
        person.bio || "",
        person.agency.name,
        person.license_id || "",
        ...(person.specialties || []),
        ...person.languages,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [agents, search, selectedSector]);

  const totalResults =
    activeTab === "all"
      ? filteredAgencies.length + filteredAgents.length
      : activeTab === "agencies"
      ? filteredAgencies.length
      : filteredAgents.length;

  const showAgencies = activeTab === "all" || activeTab === "agencies";
  const showAgents = activeTab === "all" || activeTab === "agents";

  return (
    <div className="directory-explorer-container">
      {/* Controls Bar: Search & Sector Filters */}
      <div className="directory-controls-card">
        <div className="directory-search-row">
          <div className="directory-search-input-wrap">
            <svg
              className="search-field-icon"
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              placeholder="Search by agent, agency, area, property type, or language"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="directory-search-input"
              aria-label="Search directory"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="directory-search-clear"
                aria-label="Clear search query"
              >
                ✕
              </button>
            )}
          </div>

          {/* Tab Selector */}
          <div className="directory-view-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "all"}
              onClick={() => setActiveTab("all")}
              className={`directory-tab-btn ${activeTab === "all" ? "active" : ""}`}
            >
              All ({agencies.length + agents.length})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "agencies"}
              onClick={() => setActiveTab("agencies")}
              className={`directory-tab-btn ${activeTab === "agencies" ? "active" : ""}`}
            >
              Agencies ({agencies.length})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "agents"}
              onClick={() => setActiveTab("agents")}
              className={`directory-tab-btn ${activeTab === "agents" ? "active" : ""}`}
            >
              Agents ({agents.length})
            </button>
          </div>
        </div>

        {/* Jurisdiction / Sector Chips */}
        <div className="directory-sector-filter-row">
          <span className="directory-filter-label">Area:</span>
          <div className="directory-chips-scroll">
            {SECTORS.map((sector) => (
              <button
                key={sector}
                type="button"
                onClick={() => setSelectedSector(sector)}
                className={`directory-sector-chip ${
                  selectedSector === sector ? "active" : ""
                }`}
              >
                {sector}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Results Header */}
      <p className="directory-profile-note">
        Profiles and registration details are shown for discovery. Awaaz Estate does not independently verify profile claims or a property&rsquo;s legal status.
      </p>
      <div className="directory-results-meta">
        <span className="results-count-text">
          Showing <strong>{totalResults}</strong> profiles
          {selectedSector !== "All areas" && (
            <span> in <em>{selectedSector}</em></span>
          )}
          {search && (
            <span> matching &ldquo;<strong>{search}</strong>&rdquo;</span>
          )}
        </span>

        {(search || selectedSector !== "All areas" || activeTab !== "all") && (
          <button
            type="button"
            onClick={() => {
              setSearch("");
              setSelectedSector("All areas");
              setActiveTab("all");
            }}
            className="directory-reset-filters-btn"
          >
            Reset All Filters
          </button>
        )}
      </div>

      {/* Zero Results State */}
      {totalResults === 0 && (
        <div className="directory-empty-state">
          <div className="empty-state-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
              <line x1="8" y1="11" x2="14" y2="11" />
            </svg>
          </div>
            <h3 className="empty-state-title">No matching profiles</h3>
          <p className="empty-state-desc">
            We couldn&rsquo;t find an agent or agency for that search. Try another area, language, or specialty.
          </p>
          <button
            type="button"
            onClick={() => {
              setSearch("");
              setSelectedSector("All areas");
              setActiveTab("all");
            }}
            className="empty-state-action-btn"
          >
            View Full Directory
          </button>
        </div>
      )}

      {/* Institutional Agencies Section */}
      {showAgencies && filteredAgencies.length > 0 && (
        <section className="directory-group-section">
          <div className="directory-group-header">
            <div>
              <span className="directory-kicker">Local businesses</span>
              <h2 className="directory-group-title">
                Agencies ({filteredAgencies.length})
              </h2>
            </div>
            <p className="directory-group-desc">
              Browse agencies by the areas they list as serving and contact them directly.
            </p>
          </div>

          <div className="agencies-main-grid">
            {filteredAgencies.map((org) => {
              const initials = org.name
                .split(" ")
                .map((w) => w[0])
                .join("")
                .slice(0, 2);

              const advisorCount = agents.filter(
                (a) => a.agency.slug === org.slug || a.agency.id === org.id
              ).length;

              return (
                <article key={org.id} className="agency-dossier-card">
                  <div className="agency-card-top">
                    <div className="agency-avatar">{initials}</div>
                    <div className="agency-info-heading">
                      <h3 className="agency-name">
                        <Link href={`/agencies/${org.slug}`}>{org.name}</Link>
                      </h3>
                      <div className="agency-license-tag-row">
                        <span className="agency-license-tag">Agency profile</span>
                        {org.license_number && (
                          <span className="agency-card-reg-pill">Registration details provided</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {org.address && (
                    <div className="agency-card-location">
                      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                        <circle cx="12" cy="10" r="3" />
                      </svg>
                      <span>{org.address}</span>
                    </div>
                  )}

                  <p className="agency-bio">{org.description}</p>

                  {/* Highlights Metrics */}
                  <div className="agency-card-meta-row">
                    <div className="agency-meta-item">
                      <span className="agency-meta-num">{advisorCount}</span>
                      <span className="agency-meta-label">Agents listed</span>
                    </div>
                    {org.established && (
                      <div className="agency-meta-item">
                        <span className="agency-meta-num">{org.established}</span>
                        <span className="agency-meta-label">Established</span>
                      </div>
                    )}
                  </div>

                  {/* Coverage chips */}
                  <div>
                    <span className="agency-card-sectors-title">
                      Areas listed
                    </span>
                    <div className="agency-specialties-wrap">
                      {org.coverage.map((c) => (
                        <span key={c} className="agency-spec-chip">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="agency-actions-footer">
                    <Link
                      href={`/agencies/${org.slug}`}
                      className="card-primary-action"
                    >
                      <span>View Agency Portfolio</span>
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <line x1="5" y1="12" x2="19" y2="12" />
                        <polyline points="12 5 19 12 12 19" />
                      </svg>
                    </Link>

                    <div className="card-quick-actions">
                      {org.whatsapp && (
                        <a
                          href={`https://wa.me/${cleanPhone(org.whatsapp)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="card-quick-btn card-wa-btn"
                          aria-label={`WhatsApp ${org.name}`}
                          title="WhatsApp Desk"
                        >
                          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                          </svg>
                        </a>
                      )}
                      {org.contact_phone && (
                        <a
                          href={`tel:${org.contact_phone}`}
                          className="card-secondary-action"
                          aria-label={`Call ${org.name}`}
                        >
                          Call Desk
                        </a>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {/* Agent profiles */}
      {showAgents && filteredAgents.length > 0 && (
        <section className="directory-group-section" style={{ marginTop: showAgencies && filteredAgencies.length > 0 ? 50 : 0 }}>
          <div className="directory-group-header">
            <div>
              <span className="directory-kicker">People to contact</span>
              <h2 className="directory-group-title">
                Agents ({filteredAgents.length})
              </h2>
            </div>
            <p className="directory-group-desc">
              Compare the languages, experience, and property specialties listed on each agent profile.
            </p>
          </div>

          <div className="agencies-main-grid">
            {filteredAgents.map((p) => {
              const initials = p.name
                .split(" ")
                .map((w) => w[0])
                .join("")
                .slice(0, 2);

              return (
                <article key={p.slug} className="agency-dossier-card advisor-card">
                  <div className="agency-card-top">
                    <div className="agency-avatar">{initials}</div>
                    <div className="agency-info-heading">
                      <h3 className="agency-name">
                        <Link href={`/agents/${p.slug}`}>{p.name}</Link>
                      </h3>
                      <Link
                        href={`/agencies/${p.agency.slug}`}
                        className="advisor-agency-pill-link"
                      >
                        {p.agency.name}
                      </Link>
                    </div>
                  </div>

                  {p.title && (
                    <div className="advisor-title-badge">
                      {p.title}
                    </div>
                  )}

                  {p.bio && <p className="agency-bio">{p.bio}</p>}

                  {/* Specialties chips */}
                  {p.specialties && p.specialties.length > 0 && (
                    <div>
                      <span className="agency-card-sectors-title">
                        Practice Specialties
                      </span>
                      <div className="agency-specialties-wrap">
                        {p.specialties.map((spec) => (
                          <span key={spec} className="agency-spec-chip advisor-spec-chip">
                            {spec}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="advisor-lang-row">
                    {p.languages.length > 0 && (
                      <>
                        <span className="advisor-lang-label">Languages:</span>
                        <span className="advisor-lang-val">{p.languages.join(", ")}</span>
                      </>
                    )}
                    {p.experience_years && (
                      <span className="advisor-exp-pill">{p.experience_years} years listed</span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="agency-actions-footer">
                    <Link
                      href={`/agents/${p.slug}`}
                      className="card-primary-action"
                    >
                      <span>View profile</span>
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <line x1="5" y1="12" x2="19" y2="12" />
                        <polyline points="12 5 19 12 12 19" />
                      </svg>
                    </Link>

                    <div className="card-quick-actions">
                      {p.whatsapp && (
                        <a
                          href={`https://wa.me/${cleanPhone(p.whatsapp)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="card-quick-btn card-wa-btn"
                          aria-label={`WhatsApp ${p.name}`}
                          title="WhatsApp Direct"
                        >
                          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                          </svg>
                        </a>
                      )}
                      {(p.phone || p.agency.contact_phone) && (
                        <a
                          href={`tel:${p.phone || p.agency.contact_phone}`}
                          className="card-secondary-action"
                          aria-label={`Call ${p.name}`}
                        >
                          Call Direct
                        </a>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
