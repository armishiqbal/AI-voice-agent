import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/site";
export const dynamic = "force-dynamic";
export default function robots(): MetadataRoute.Robots { return { rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/staff", "/agency/", "/account", "/properties?*min_price", "/properties?*max_price", "/properties?*amenities", "/properties?*sort", "/properties?*west", "/properties?*east", "/properties?*south", "/properties?*north"] }, sitemap: `${siteUrl}/sitemap.xml` }; }
