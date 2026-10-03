import Link from "next/link";
export default function NotFound() { return <section className="section container prose"><p className="eyebrow">Page not found</p><h1>This page is unavailable</h1><p>The address may have changed or the listing may no longer be published.</p><Link className="button" href="/properties">Explore current listings</Link></section>; }
