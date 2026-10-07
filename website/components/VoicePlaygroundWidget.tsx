"use client";

import { useState } from "react";
import Link from "next/link";

interface SamplePrompt {
  id: string;
  userQuery: string;
  agentResponse: string;
  propertyTitle: string;
  propertyPrice: string;
  propertyArea: string;
  propertySpecs: string;
  propertySlug: string;
}

export function VoicePlaygroundWidget() {
  const samplePrompts: SamplePrompt[] = [
    {
      id: "villas",
      userQuery: "Show 1 Kanal modern villas in DHA Phase 2 under 8 Crore",
      agentResponse:
        "Ji bilkul! DHA Phase 2 Sector B mein 1 Kanal designer villa available hai for PKR 7.8 Crore. 5 master bedrooms, imported kitchen, private lawn, aur confirmed CDA/DHA transfer allotment hai. Kya aap iska site tour schedule karna chahein gay?",
      propertyTitle: "1 Kanal Modern Luxury Villa with Landscaped Lawn",
      propertyPrice: "PKR 7.8 Crore",
      propertyArea: "Sector B, DHA Phase 2, Islamabad",
      propertySpecs: "5 Beds · 6 Baths · 4,500 sq ft (1 Kanal)",
      propertySlug: "1-kanal-modern-luxury-villa-dha-phase-2-islamabad",
    },
    {
      id: "apartments",
      userQuery: "Find 3-bed luxury apartments in F-10 under 2.5 Lakh per month",
      agentResponse:
        "I found a high-floor corner apartment in Sector F-10 with direct Margalla views, 24/7 power backup, and basement parking for PKR 2.2 Lakh/month. Ready for immediate lease.",
      propertyTitle: "Corner Executive Penthouse Suite with Margalla Hills View",
      propertyPrice: "PKR 2.2 Lakh / mo",
      propertyArea: "Sector F-10 Markaz, Islamabad",
      propertySpecs: "3 Beds · 3 Baths · 2,800 sq ft",
      propertySlug: "corner-executive-penthouse-suite-f10-islamabad",
    },
    {
      id: "cda",
      userQuery: "Is Bahria Town Phase 7 approved by CDA and safe to invest?",
      agentResponse:
        "Bahria Town Phase 7 is approved under RDA planning jurisdiction with completed infrastructure, uninterrupted utilities, and fast connectivity to GT Road. Our catalog only includes verified non-encumbrance properties.",
      propertyTitle: "10 Marla Mediterranean Residence near River View Commercial",
      propertyPrice: "PKR 3.4 Crore",
      propertyArea: "Phase 7, Bahria Town, Rawalpindi",
      propertySpecs: "4 Beds · 4 Baths · 2,250 sq ft (10 Marla)",
      propertySlug: "10-marla-mediterranean-residence-bahria-town-phase-7",
    },
  ];

  const [selectedPrompt, setSelectedPrompt] = useState<SamplePrompt>(samplePrompts[0]);

  return (
    <div className="voice-playground-card">
      <div className="playground-glow-backdrop" aria-hidden="true" />

      <div className="playground-layout-grid">
        {/* Left Column: Explanatory & Interactive Prompt Triggers */}
        <div className="playground-left-col">
          <div className="playground-badge">
            <span className="live-pulse-dot" />
            <span>Interactive Voice AI Concierge · Urdu & English</span>
          </div>

          <h2 className="playground-heading">
            Skip the manual filters. <br />
            <span className="playground-gradient-text">Just speak to Awaaz.</span>
          </h2>

          <p className="playground-sub">
            Describe your requirements naturally in Urdu, English, or Roman Urdu. Our conversational assistant analyzes vetted catalog records, clarifies CDA allotment rules, and schedules site tours on the spot.
          </p>

          <div className="playground-prompts-picker">
            <span className="picker-title">Tap to test voice intelligence:</span>
            <div className="picker-list">
              {samplePrompts.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`prompt-trigger-chip ${selectedPrompt.id === item.id ? "active" : ""}`}
                  onClick={() => setSelectedPrompt(item)}
                >
                  <span className="prompt-chip-quote">“</span>
                  <span className="prompt-chip-text">{item.userQuery}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Soundwave Animation & Primary CTA Button */}
          <div className="playground-action-row">
            <Link href="/assistant" className="voice-studio-launch-btn">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="22" />
              </svg>
              <span>Launch Live Voice Studio →</span>
            </Link>

            <div className="soundwave-bars" aria-hidden="true">
              <span className="sw-bar bar-1" />
              <span className="sw-bar bar-2" />
              <span className="sw-bar bar-3" />
              <span className="sw-bar bar-4" />
              <span className="sw-bar bar-5" />
              <span className="sw-bar bar-6" />
              <span className="sw-bar bar-7" />
            </div>
          </div>
        </div>

        {/* Right Column: Live Conversation Simulation Showcase */}
        <div className="playground-right-col">
          <div className="simulated-dialogue-window">
            <div className="dialogue-header">
              <div className="dialogue-header-left">
                <div className="mini-orb-pulse" />
                <span className="agent-status-label">Awaaz Neural Voice Active</span>
              </div>
              <span className="dialogue-lang-tag">Urdu & English</span>
            </div>

            <div className="dialogue-body">
              {/* User Speech Bubble */}
              <div className="speech-bubble-row user">
                <div className="speech-bubble user-bubble">
                  <div className="bubble-speaker-label">You (Voice Input)</div>
                  <p className="bubble-text">“{selectedPrompt.userQuery}”</p>
                </div>
              </div>

              {/* Assistant Response Bubble */}
              <div className="speech-bubble-row agent">
                <div className="speech-bubble agent-bubble">
                  <div className="bubble-speaker-label">
                    <span>Awaaz Voice Concierge</span>
                    <span className="verified-badge-mini">Verified Inventory RAG</span>
                  </div>
                  <p className="bubble-text">{selectedPrompt.agentResponse}</p>

                  {/* Inline Recommended Property Card */}
                  <div className="dialogue-property-card">
                    <div className="card-mini-specs">
                      <span className="property-tag-mini">Verified Match</span>
                      <h4 className="property-title-mini">{selectedPrompt.propertyTitle}</h4>
                      <p className="property-loc-mini">
                        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ display: "inline-block", verticalAlign: "middle", marginRight: 5 }}>
                          <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
                          <circle cx="12" cy="10" r="3" />
                        </svg>
                        {selectedPrompt.propertyArea}
                      </p>
                      <p className="property-specs-mini">
                        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ display: "inline-block", verticalAlign: "middle", marginRight: 5 }}>
                          <rect width="18" height="18" x="3" y="3" rx="2" />
                          <path d="M3 9h18M9 21V9" />
                        </svg>
                        {selectedPrompt.propertySpecs}
                      </p>
                      <div className="card-mini-footer">
                        <span className="property-price-mini">{selectedPrompt.propertyPrice}</span>
                        <Link
                          className="button small primary mini-tour-btn"
                          href="/assistant"
                          title="Speak to assistant to book tour"
                        >
                          Book Viewing with Voice →
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
