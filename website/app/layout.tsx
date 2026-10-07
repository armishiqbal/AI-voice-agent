import type { Metadata } from "next";
import Link from "next/link";
import { siteUrl } from "@/lib/site";
import { SiteHeader } from "@/components/SiteHeader";
import { ComparisonTray } from "@/components/ComparisonTray";
import {Source_Serif_4, Plus_Jakarta_Sans} from "next/font/google";
import "./globals.css";
const serif=Source_Serif_4({subsets:["latin"],variable:"--font-serif",display:"swap"});
const sans=Plus_Jakarta_Sans({subsets:["latin"],variable:"--font-sans",display:"swap"});

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: { default: "Awaaz Estate | Property discovery in Pakistan", template: "%s | Awaaz Estate" },
  description: "Explore published listings, compare property facts and arrange your next step.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${serif.variable} ${sans.variable}`}>
        <SiteHeader />

        <main id="main">{children}</main>

        <footer className="site-footer">
          <div className="container footer-grid">
            <div className="footer-col-brand">
              <Link className="footer-brand" href="/">
                Awaaz<span className="brand-accent">Estate</span>
              </Link>
              <p className="footer-desc">
                Browse published agency property listings, or use the multilingual voice assistant to explore the catalog.
              </p>
              <div className="footer-trust-badge">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <path d="m9 12 2 2 4-4" />
                </svg>
                <span>Published listings from approved agencies</span>
              </div>
            </div>

            <div className="footer-col">
              <h4>Properties</h4>
              <nav aria-label="Footer properties navigation">
                <Link href="/properties">All Listings</Link>
                <Link href="/properties?transaction_type=sale">Homes for Sale</Link>
                <Link href="/properties?transaction_type=rent">Properties for Rent</Link>
                <Link href="/service-area">Service areas</Link>
                <Link href="/shortlist">Your Shortlist</Link>
                <Link href="/agents">Agents</Link>
                <Link href="/areas">Area guides</Link>
              </nav>
            </div>

            <div className="footer-col">
              <h4>Tools & Assistance</h4>
              <nav aria-label="Footer tools navigation">
                <Link href="/compare">Property Comparison</Link>
                <Link href="/assistant">Property assistant</Link>
                <Link href="/account">Your account</Link>
                <Link href="/contact">Contact</Link>
              </nav>
            </div>

            <div className="footer-col">
              <h4>Company & Legal</h4>
              <nav aria-label="Footer company navigation">
                <Link href="/about">About Awaaz Estate</Link>
                <Link href="/privacy">Privacy Policy</Link>
                <Link href="/terms">Terms of Service</Link>
                <p className="footer-contact-info">
                  Coverage varies by approved agency profile and published inventory.
                </p>
              </nav>
            </div>
          </div>

          <div className="footer-bottom container">
            <p>© {new Date().getFullYear()} Awaaz Estate. Property availability can change; contact our team to confirm a listing.</p>
            <p className="footer-motto">Built with transparency and modern real-estate technology.</p>
          </div>
        </footer>

        {/* Global Floating Property Comparison Tray */}
        <ComparisonTray />
      </body>
    </html>
  );
}
