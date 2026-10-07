import Link from "next/link";
import { listings, type SearchParams, CatalogError } from "@/lib/catalog";
import { metadata } from "@/lib/site";
import { PropertiesCatalogContainer } from "@/components/PropertiesCatalogContainer";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const p = await searchParams;
  const isFiltered = Object.keys(p).some((k) => !["page", "sort", "view"].includes(k));
  return {
    ...metadata(
      "Explore Verified Properties · Awaaz Estate",
      "Search physical on-site verified houses, apartments, plots, and commercial properties across Islamabad and Rawalpindi.",
      `/properties${p.page ? `?page=${p.page}` : ""}`
    ),
    ...(isFiltered ? { robots: { index: false, follow: true } } : {}),
  };
}

export default async function PropertiesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  let errorMessage: string | null = null;
  let isValidationError = false;

  const catalog = await listings(params).catch((err: unknown) => {
    if (err instanceof CatalogError && err.status === 422) {
      isValidationError = true;
      errorMessage = "The search filters you entered could not be processed. Please check your price or size ranges.";
    } else {
      errorMessage = "The property catalog service is temporarily unreachable. Please retry shortly.";
    }
    return null;
  });

  const properties = catalog?.data ?? [];
  const total = catalog?.pagination.total ?? 0;
  const page = catalog?.pagination.page ?? 1;
  const totalPages = catalog?.pagination.total_pages ?? 1;

  return (
    <div className="section container catalog-page-container">
      <header className="catalog-header-luxury">
        <nav className="breadcrumbs-modern" aria-label="Breadcrumb">
          <Link href="/">Home</Link>
          <span className="bc-sep">/</span>
          <span className="bc-current">Properties</span>
        </nav>
        <div className="catalog-header-text">
          <span className="section-eyebrow">Verified Catalog</span>
          <h1 className="catalog-title">Explore Verified Real Estate</h1>
          <p className="catalog-sub">
            Direct agency inventory with independent legal title scrutiny, physical on-site photography, and transparent transaction pricing.
          </p>
        </div>
      </header>

      <PropertiesCatalogContainer
        params={params}
        properties={properties}
        total={total}
        page={page}
        totalPages={totalPages}
        errorMessage={errorMessage}
        isValidationError={isValidationError}
      />
    </div>
  );
}
