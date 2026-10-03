import Link from "next/link";
export function Notice({ error = false, title, children }: { error?: boolean; title: string; children: React.ReactNode }) {
  return <div className={`notice ${error ? "error" : ""}`} role={error ? "alert" : undefined}><h2>{title}</h2>{children}{error && <p><Link className="text-link" href="/properties">Try the property search again</Link></p>}</div>;
}
