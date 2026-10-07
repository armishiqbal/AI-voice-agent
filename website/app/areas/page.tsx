import Link from "next/link";
import { guides } from "@/lib/marketplace";
import { metadata } from "@/lib/site";
import { AreasExplorer } from "@/components/AreasExplorer";
import { SECTOR_METADATA_MAP, getSectorMetadata, type SectorDossierMeta } from "@/lib/sectors";

export const dynamic = "force-dynamic";

export const generateMetadata = () =>
  metadata(
    "Area Guides | Awaaz Estate",
    "Explore area guides across Islamabad and Rawalpindi, then browse current property listings in the locations you like.",
    "/areas"
  );

export default async function AreasPage() {
  const guideList = await guides().catch(() => []);
  const sectorMap = new Map<string, SectorDossierMeta>(Object.entries(SECTOR_METADATA_MAP));

  for (const guide of guideList) {
    const key = `${guide.city_slug}/${guide.area_slug}`;
    if (!sectorMap.has(key)) {
      sectorMap.set(key, getSectorMetadata(guide.city_slug, guide.area_slug));
    }
  }

  return (
    <main className="areas-page-shell">
      <section className="areas-page-hero" aria-labelledby="areas-page-title">
        <div className="areas-page-hero-copy">
          <p className="areas-page-eyebrow">Area guides · Islamabad &amp; Rawalpindi</p>
          <h1 id="areas-page-title">Find an area that feels like <em>your next move.</em></h1>
          <p className="areas-page-intro">
            Get a feel for each location, compare the guides, then check current listings when an area stands out.
          </p>
          <div className="areas-page-actions">
            <Link className="areas-page-primary-link" href="/properties">Browse properties</Link>
            <Link className="areas-page-secondary-link" href="/assistant">Ask Awaaz about an area <span aria-hidden="true">→</span></Link>
          </div>
        </div>
        <aside className="areas-page-note" aria-label="About these area guides">
          <span className="areas-page-note-mark" aria-hidden="true">A</span>
          <div>
            <strong>A useful starting point</strong>
            <p>Area guides are general information. Prices, availability, commute times, and legal status can change; confirm them against current listings and the relevant authority.</p>
          </div>
        </aside>
      </section>

      <section className="areas-discovery-section" aria-labelledby="areas-discovery-title">
        <div className="areas-discovery-heading">
          <div>
            <p className="areas-page-eyebrow">Explore the neighbourhoods</p>
            <h2 id="areas-discovery-title">Where would you like to look?</h2>
          </div>
          <p>Search by area name or narrow the guides by city and area type.</p>
        </div>
        <AreasExplorer initialSectors={Array.from(sectorMap.values())} />
      </section>

      <section className="areas-next-step" aria-labelledby="areas-next-title">
        <div>
          <p className="areas-page-eyebrow">Before you decide</p>
          <h2 id="areas-next-title">Check the property, not just the area.</h2>
          <p>Confirm the current price, availability, ownership documents, dues, and transfer process for the specific property with the relevant authority and seller.</p>
        </div>
        <Link className="areas-page-primary-link" href="/properties">See current listings <span aria-hidden="true">→</span></Link>
      </section>
    </main>
  );
}
