import Link from "next/link";
import { listing, listings, scalar, type Listing, type SearchParams } from "@/lib/catalog";
import { metadata } from "@/lib/site";
import { Notice } from "@/components/Notice";
import { PropertyComparisonMatrix } from "@/components/PropertyComparisonMatrix";

export const dynamic = "force-dynamic";

export const generateMetadata = () => ({
  ...metadata(
    "Compare properties",
    "Compare published asking prices, size, location, availability, rental periods, and listing review information.",
    "/compare"
  ),
  robots: { index: false, follow: true },
});

export default async function ComparePage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const raw = params.slugs;
  const slugs = [...new Set((Array.isArray(raw) ? raw : scalar(raw).split(",")).filter(Boolean))].slice(0, 3);

  const [options, selected] = await Promise.all([
    listings({ page_size: "100" }).catch(() => null),
    Promise.all(slugs.map((slug) => listing(slug).catch(() => null))),
  ]);

  const properties = selected.filter((value): value is Listing => value !== null);
  const choices = [...new Map([...(options?.data || []), ...properties].map((property) => [property.slug, property])).values()];

  return (
    <section className="section container compare-page-root">
      <div className="compare-header">
        <p className="eyebrow">Decision Matrix</p>
        <h1 className="compare-title">Compare properties</h1>
        <p className="compare-subtitle">
          Evaluate up to three published listings side by side. Compare their submitted facts and review information, then contact the publisher with any questions.
        </p>
      </div>

      {selected.some((item) => item === null) && (
        <div style={{ marginBottom: 20 }}>
          <Notice error title="Some listings could not be loaded">
            <p>One or more selected listings may have been unlisted or are temporarily unavailable.</p>
          </Notice>
        </div>
      )}

      {choices.length === 0 ? (
        <Notice title="No properties currently available to compare">
            <p>Browse the catalog to find properties to add to your comparison.</p>
          <div style={{ marginTop: 16 }}>
            <Link className="button primary" href="/properties">
              Browse Properties
            </Link>
          </div>
        </Notice>
      ) : (
        <PropertyComparisonMatrix properties={properties} choices={choices} />
      )}
    </section>
  );
}
