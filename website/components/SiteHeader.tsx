"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShortlistBadge } from "./ShortlistBadge";

export function SiteHeader() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  // Close mobile drawer on route navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Handle scroll shadow enhancement
  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navLinks = [
    { href: "/properties", label: "Properties" },
    { href: "/areas", label: "Area Guides" },
    { href: "/agents", label: "Agents" },
    { href: "/sell", label: "Sell" },
    { href: "/contact", label: "Contact" },
  ];

  const isActive = (href: string) => {
    if (href === "/properties" && pathname.startsWith("/properties")) return true;
    if (href === "/areas" && pathname.startsWith("/areas")) return true;
    if (href === "/agents" && (pathname.startsWith("/agents") || pathname.startsWith("/agencies"))) return true;
    return pathname === href;
  };

  return (
    <>
      <header className={`site-header ${scrolled ? "scrolled" : ""}`}>
        <div className="container header-inner">
          {/* Brand Identity */}
          <Link className="brand" href="/" aria-label="Awaaz Estate home">
            <span className="brand-symbol" aria-hidden="true">
              A
            </span>
            <span className="brand-text">
              Awaaz<span className="brand-accent">Estate</span>
            </span>
          </Link>

          {/* Desktop Navigation */}
          <nav className="main-nav desktop-nav" aria-label="Main navigation">
            {navLinks.map((item) => (
              <Link
                key={item.href}
                className={`nav-link ${isActive(item.href) ? "active" : ""}`}
                href={item.href}
              >
                {item.label}
              </Link>
            ))}

            <div className="nav-divider-v" aria-hidden="true" />

            <ShortlistBadge />

            <Link className="ai-voice-nav-btn" href="/assistant">
              <span className="ai-sparkle-dot" aria-hidden="true" />
              <span>AI Concierge</span>
            </Link>
          </nav>

          {/* Mobile Right Controls: Shortlist + Menu Toggle */}
          <div className="mobile-header-actions">
            <ShortlistBadge />

            <button
              type="button"
              className={`mobile-menu-btn ${mobileOpen ? "open" : ""}`}
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={mobileOpen}
            >
              <span className="hamburger-line line-1" />
              <span className="hamburger-line line-2" />
              <span className="hamburger-line line-3" />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Drawer Overlay */}
      {mobileOpen && (
        <div
          className="mobile-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Navigation Drawer */}
      <aside
        className={`mobile-drawer ${mobileOpen ? "open" : ""}`}
        aria-label="Mobile navigation"
      >
        <div className="mobile-drawer-header">
          <Link className="brand" href="/" onClick={() => setMobileOpen(false)}>
            <span className="brand-symbol" aria-hidden="true">
              A
            </span>
            <span className="brand-text">
              Awaaz<span className="brand-accent">Estate</span>
            </span>
          </Link>
          <button
            type="button"
            className="mobile-drawer-close"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu"
          >
            ×
          </button>
        </div>

        <nav className="mobile-drawer-nav">
          {navLinks.map((item) => (
            <Link
              key={item.href}
              className={`mobile-nav-link ${isActive(item.href) ? "active" : ""}`}
              href={item.href}
              onClick={() => setMobileOpen(false)}
            >
              {item.label}
            </Link>
          ))}
          <Link
            className="mobile-nav-link"
            href="/compare"
            onClick={() => setMobileOpen(false)}
          >
            Property Comparison
          </Link>
          <Link
            className="mobile-nav-link"
            href="/account"
            onClick={() => setMobileOpen(false)}
          >
            Client Workspace
          </Link>
        </nav>

        <div className="mobile-drawer-footer">
          <Link
            className="ai-voice-nav-btn mobile-cta-btn"
            href="/assistant"
            onClick={() => setMobileOpen(false)}
          >
            <span className="ai-sparkle-dot" aria-hidden="true" />
            <span>Launch AI Voice Concierge</span>
          </Link>

          <p className="mobile-drawer-note">
            Direct audited agency inventory across Islamabad & Rawalpindi.
          </p>
        </div>
      </aside>
    </>
  );
}
