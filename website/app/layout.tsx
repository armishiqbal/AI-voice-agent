import type { Metadata } from "next";
import Link from "next/link";
import { siteUrl } from "@/lib/site";
import "./globals.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: { default: "Awaaz Estate | Find your next place", template: "%s | Awaaz Estate" },
  description: "Explore company property listings and request a viewing with Awaaz Estate.",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="site-header"><div className="container header-inner">
      <Link className="brand" href="/" aria-label="Awaaz Estate home"><span className="brand-symbol" aria-hidden="true">A</span>Awaaz<span>Estate</span></Link>
      <nav aria-label="Main navigation"><Link href="/properties">Find a property</Link><Link href="/about">About us</Link><Link href="/contact">Contact</Link><a className="button small" href="/assistant/">Ask Awaaz</a></nav>
    </div></header>
    <main id="main">{children}</main>
    <footer className="site-footer"><div className="container footer-inner"><div><Link className="footer-brand" href="/">Awaaz Estate</Link><p>Find a place. Ask a question. Plan your visit.</p></div><nav aria-label="Footer navigation"><Link href="/service-area">Service area</Link><Link href="/compare">Compare</Link><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/staff">Staff</Link></nav></div></footer>
  </body></html>;
}
