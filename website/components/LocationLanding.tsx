import Link from "next/link";
import { notFound } from "next/navigation";
import { listings, areaGuide } from "@/lib/catalog";
import { PropertiesCatalogContainer } from "./PropertiesCatalogContainer";

export const cities: Record<string, string> = {
  islamabad: "Islamabad",
  rawalpindi: "Rawalpindi",
  lahore: "Lahore",
  karachi: "Karachi",
};

export async function LocationLanding({
  city,
  area,
  transaction,
}: {
  city: string;
  area?: string;
  transaction: "sale" | "rent";
}) {
  const name = cities[city.toLowerCase()];
  if (!name) notFound();
  const guide = area ? await areaGuide(city, area) : null;
  if (area && !guide) notFound();

  const params = {
    city: name,
    area: area || "",
    transaction_type: transaction,
  };
  const r = await listings(params).catch(() => null);

  const title = `${transaction === "sale" ? "Property for Sale" : "Property for Rent"} in ${guide?.title || name}`;

  return (
    <div className="section container catalog-page-container">
      <header className="catalog-header-luxury">
        <nav className="breadcrumbs-modern" aria-label="Breadcrumb">
          <Link href="/">Home</Link>
          <span className="bc-sep">/</span>
          <Link href="/properties">Properties</Link>
          <span className="bc-sep">/</span>
          <span className="bc-current">{name}</span>
        </nav>
        <div className="catalog-header-text">
          <span className="section-eyebrow">
            {transaction === "sale" ? "Residential & Commercial Sales" : "Executive Leasing"}
          </span>
          <h1 className="catalog-title">{title}</h1>
          {guide?.overview_markdown && (
            <p className="catalog-sub">{guide.overview_markdown}</p>
          )}
        </div>
      </header>

      <PropertiesCatalogContainer
        params={params}
        properties={r?.data ?? []}
        total={r?.pagination.total ?? 0}
        page={r?.pagination.page ?? 1}
        totalPages={r?.pagination.total_pages ?? 1}
        errorMessage={r ? null : "The property service is temporarily unavailable."}
      />
    </div>
  );
}
