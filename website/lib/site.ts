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
export function label(value: string): string { return value.replace(/[_-]/g, " "); }
