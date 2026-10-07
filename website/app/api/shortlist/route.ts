import { NextRequest, NextResponse } from "next/server";
import { listing, type Listing } from "@/lib/catalog";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const raw = searchParams.get("slugs") || "";
  const slugs = [...new Set(raw.split(",").map((s) => s.trim()).filter(Boolean))].slice(0, 25);

  if (slugs.length === 0) {
    return NextResponse.json({ data: [] });
  }

  const results = await Promise.all(
    slugs.map((slug) => listing(slug).catch(() => null))
  );

  const data = results.filter((item): item is Listing => item !== null);
  return NextResponse.json({ data });
}
