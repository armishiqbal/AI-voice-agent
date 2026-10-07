"use client";

import { useState } from "react";
import { Listing } from "@/lib/catalog";

interface CivicTitleAuditWidgetProps {
  property: Listing;
  onRequestLegalFile?: () => void;
}

export function CivicTitleAuditWidget({
  property,
  onRequestLegalFile,
}: CivicTitleAuditWidgetProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  // Determine governing authority based on area & city
  const area = property.area.toLowerCase();
  const isDha = area.includes("dha");
  const isBahria = area.includes("bahria");
  const isGulberg = area.includes("gulberg");
  const isCda = !isDha && !isBahria && !isGulberg && property.city.toLowerCase() === "islamabad";

  const authorityName = isDha
    ? "Defence Housing Authority (DHA Islamabad-Rawalpindi)"
    : isBahria
    ? "Bahria Town Head Office Record Transfer Directorate"
    : isGulberg
    ? "IBECHS / Gulberg Administration (CDA Approved Layout)"
    : isCda
    ? "Capital Development Authority (CDA Estate Management-I)"
    : "Rawalpindi Development Authority / Revenue Sub-Registrar";

  const authorityCode = isDha ? "DHA" : isBahria ? "Bahria" : isGulberg ? "IBECHS" : isCda ? "CDA" : "RDA";

  const isVerified = property.verification?.status === "verified";
  const isReviewed = property.verification?.status === "reviewed" || isVerified;

  const pillars = [
    {
      title: "Primary Title & Allotment Register",
      status: isReviewed ? "Verified" : "Pending Verification",
      authority: `${authorityCode} Transfer Register`,
      description: `Authentication of allotment letter or registered transfer deed directly against official ${authorityCode} files. Confirms seller is the legal title holder with full disposal rights.`,
      icon: (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      ),
    },
    {
      title: "Non-Encumbrance Status (NEC)",
      status: isVerified ? "Zero Liens Confirmed" : "Legal Scrutiny Available",
      authority: "Revenue & Banking Clearance",
      description: "Verification that the title is free of bank mortgages, financial hypothecation, excise property tax dues, and civil court stay orders.",
      icon: (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <polyline points="9 12 11 14 15 10" />
        </svg>
      ),
    },
    {
      title: "Building Plan & Completion Approval",
      status: property.property_type === "plot" ? "Layout Plan (LOP) Cleared" : isReviewed ? "Structural Plan Approved" : "Subject to Survey",
      authority: `${authorityCode} Building Control`,
      description: property.property_type === "plot"
        ? `Demarcated plot conforming to the approved Layout Plan (LOP) with valid road widening and greenbelt setback clearance.`
        : `Covered area, floor area ratio (FAR), and building height surveyed against ${authorityCode} Building Control bylaws.`,
      icon: (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          <rect width="18" height="18" x="3" y="3" rx="2" />
          <path d="M3 9h18M9 21V9" />
        </svg>
      ),
    },
    {
      title: "Civic Utility Sanctions",
      status: isVerified ? "Active Connections" : "Verified Upon Request",
      authority: "IESCO / SNGPL / Municipal",
      description: "Verification of dedicated electric meter billing (IESCO), sanctioned gas meter (SNGPL), and authorized water connection or sweet-water boring clearance.",
      icon: (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
        </svg>
      ),
    },
    {
      title: "Physical Demarcation & Boundary Pegging",
      status: isVerified ? "On-Site Surveyed" : "Survey Available",
      authority: "Awaaz Inspection Engineering",
      description: "On-ground physical survey confirming boundary wall coordinates, total covered area, access road width, and absence of civic encroachments.",
      icon: (
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="22" y1="12" x2="18" y2="12" />
          <line x1="6" y1="12" x2="2" y2="12" />
          <line x1="12" y1="6" x2="12" y2="2" />
          <line x1="12" y1="22" x2="12" y2="18" />
        </svg>
      ),
    },
  ];

  return (
    <div className="civic-audit-card">
      <div className="audit-header-strip">
        <div className="audit-title-box">
          <span className="audit-kicker">Legal &amp; Title Due Diligence</span>
          <h3 className="audit-title">Civic Title Audit Scorecard</h3>
        </div>
        <div className="audit-authority-badge">
          <span className="authority-dot" />
          <span>{authorityCode} Jurisdiction</span>
        </div>
      </div>

      <div className="audit-authority-meta">
        <span className="meta-label">Governing Civic Authority:</span>
        <strong className="meta-val">{authorityName}</strong>
      </div>

      <p className="audit-intro">
        Awaaz Estate applies rigorous 5-point legal and physical scrutiny to protect private buyers, overseas Pakistani investors, and institutional clients from title disputes.
      </p>

      {/* 5-Pillar Scorecard Grid */}
      <div className="audit-pillars-list">
        {pillars.map((pillar, idx) => {
          const isOpen = expandedIndex === idx;

          return (
            <div
              key={pillar.title}
              className={`audit-pillar-row ${isOpen ? "open" : ""}`}
              onClick={() => setExpandedIndex(isOpen ? null : idx)}
              role="button"
              tabIndex={0}
            >
              <div className="pillar-row-header">
                <div className="pillar-row-left">
                  <div className="pillar-icon-wrap" aria-hidden="true">
                    {pillar.icon}
                  </div>
                  <div>
                    <h4 className="pillar-title">{pillar.title}</h4>
                    <span className="pillar-auth-sub">{pillar.authority}</span>
                  </div>
                </div>

                <div className="pillar-row-right">
                  <span
                    className={`pillar-status-chip ${
                      pillar.status.includes("Verified") || pillar.status.includes("Confirmed") || pillar.status.includes("Surveyed") || pillar.status.includes("Cleared")
                        ? "verified"
                        : "available"
                    }`}
                  >
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>{pillar.status}</span>
                  </span>
                  <span className="pillar-chevron-indicator">
                    <svg
                      viewBox="0 0 24 24"
                      width="16"
                      height="16"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </span>
                </div>
              </div>

              {isOpen && (
                <div className="pillar-detail-body">
                  <p>{pillar.description}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="audit-card-footer">
        <div className="audit-guarantee-note">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            <polyline points="9 12 11 14 15 10" />
          </svg>
          <span>
            Every accepted offer is held in escrow until independent verification at the {authorityCode} transfer window.
          </span>
        </div>

        {onRequestLegalFile && (
          <button
            type="button"
            className="button secondary audit-request-btn"
            onClick={onRequestLegalFile}
          >
            Request Complete Title Dossier
          </button>
        )}
      </div>
    </div>
  );
}
