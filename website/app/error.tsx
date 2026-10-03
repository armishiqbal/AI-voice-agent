"use client";
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <section className="section container"><h1>We could not load this page</h1><p>Please try again. Your browser can still return to the property search.</p><button className="button" onClick={reset}>Try again</button></section>; }
