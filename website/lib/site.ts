import type { Metadata } from "next";

export const siteUrl = (process.env.SITE_URL || process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/+$/, "");
export function metadata(title: string, description: string, path: string): Metadata {
  return { title, description, alternates: { canonical: path }, openGraph: {
    title, description, url: `${siteUrl}${path}`, siteName: "Awaaz Estate", type: "website",
  } };
}
export function price(value: number): string {
  return `PKR ${new Intl.NumberFormat("en-PK", { maximumFractionDigits: 0 }).format(value)}`;
}
export function formatPkrShort(value: number): string {
  if (value >= 10000000) {
    const cr = value / 10000000;
    const formatted = cr >= 10 ? cr.toFixed(1) : cr.toFixed(2);
    return `PKR ${formatted.replace(/\.0$/, "")} Crore`;
  }
  if (value >= 100000) {
    const lakh = value / 100000;
    const formatted = lakh >= 10 ? lakh.toFixed(1) : lakh.toFixed(2);
    return `PKR ${formatted.replace(/\.0$/, "")} Lakh`;
  }
  return `PKR ${new Intl.NumberFormat("en-PK").format(value)}`;
}
export function label(value: string): string { return value.replace(/[_-]/g, " "); }

export function formatPropertySize(sqft: number, propertyType?: string, sqftPerMarla?: number | null): string {
  const canonical = `${sqft.toLocaleString("en-PK")} sq ft`;
  if (!sqft || sqft <= 0) return canonical;

  const factor = sqftPerMarla && sqftPerMarla > 0 ? sqftPerMarla : 225;
  // Marla & Kanal are traditional Pakistani land & residential units (1 Kanal = 20 Marla = 4,500 sq ft in Islamabad CDA)
  const isLanded = !propertyType || ["house", "plot"].includes(propertyType.toLowerCase());
  if (isLanded) {
    const marlas = sqft / factor;
    if (marlas >= 20) {
      const kanals = marlas / 20;
      const formattedKanal = Number.isInteger(kanals) ? kanals.toString() : kanals.toFixed(1).replace(/\.0$/, "");
      return `${formattedKanal} Kanal (${canonical})`;
    }
    if (marlas >= 1) {
      const formattedMarla = Number.isInteger(marlas) ? marlas.toString() : marlas.toFixed(1).replace(/\.0$/, "");
      return `${formattedMarla} Marla (${canonical})`;
    }
  }

  return canonical;
}
