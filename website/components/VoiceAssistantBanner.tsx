"use client";

import Link from "next/link";

export function VoiceAssistantBanner() {
  const examplePrompts = [
    { label: "Show 1 Kanal villas in DHA Phase 2 under 8 Crore", query: "Show 1 Kanal villas in DHA Phase 2 under 8 Crore" },
    { label: "Find 3-bed modern apartments for rent in F-10", query: "Find 3-bed modern apartments for rent in F-10" },
    { label: "Are there any reviewed commercial plots in Gulberg?", query: "Are there any reviewed commercial plots in Gulberg?" },
  ];

  return (
    <div className="voice-banner-card">
      <div className="voice-banner-glow" aria-hidden="true" />
      <div className="voice-banner-content">
        <div className="voice-badge">
          <span className="voice-pulse-dot" />
          <span>Multilingual AI Voice Concierge · Urdu &amp; English</span>
        </div>

        <h2 className="voice-heading">
          Skip the search filters. <br />
          <em>Just speak to Awaaz.</em>
        </h2>

        <p className="voice-desc">
          Describe your dream home in your own words. Our AI assistant analyzes published inventory, clarifies floor plans, explains CDA/RDA regulations, and schedules viewings directly.
        </p>

        <div className="voice-prompts">
          <span className="voice-prompt-title">Try asking or tap to speak:</span>
          <div className="voice-prompt-chips">
            {examplePrompts.map((item) => (
              <Link
                key={item.query}
                href={`/assistant?q=${encodeURIComponent(item.query)}`}
                className="voice-prompt-chip"
                style={{ textDecoration: "none" }}
              >
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                </svg>
                <span>&ldquo;{item.label}&rdquo;</span>
              </Link>
            ))}
          </div>
        </div>

        <div className="voice-cta-row">
          <Link href="/assistant" className="voice-primary-btn">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="22" />
            </svg>
            <span>Start Voice Conversation</span>
          </Link>

          {/* Sound waves animation */}
          <div className="voice-soundwave" aria-hidden="true">
            <span className="wave-bar bar-1" />
            <span className="wave-bar bar-2" />
            <span className="wave-bar bar-3" />
            <span className="wave-bar bar-4" />
            <span className="wave-bar bar-5" />
            <span className="wave-bar bar-6" />
            <span className="wave-bar bar-7" />
          </div>
        </div>
      </div>
    </div>
  );
}
