import Link from "next/link";
import { listings } from "@/lib/catalog";
import { metadata } from "@/lib/site";
import { SearchForm } from "@/components/SearchForm";
import { ListingCard } from "@/components/ListingCard";
import { Notice } from "@/components/Notice";
export const dynamic = "force-dynamic";
export const generateMetadata = () => metadata("Find your next place", "Explore Awaaz Estate company listings, compare properties and request a viewing.", "/");
export default async function Home() {
  const catalog = await listings({ page_size: "6", sort: "newest" }).catch(() => null);
  return <>
    <section className="hero"><div className="container"><div className="hero-copy"><p className="eyebrow">Awaaz Estate · Your property search</p><h1>A place for your<br /><em>next chapter.</em></h1><p>Explore homes, plots and commercial spaces. See the details, ask a question and take the next step with our team.</p></div><SearchForm /><p className="quiet" style={{ marginTop: 18 }}>Prefer to talk it through? <Link href="/assistant">Ask our voice assistant</Link>.</p></div></section>
    <section className="section container"><div className="section-heading"><div><h2>Explore our listings</h2><p>Company properties, with availability shown clearly.</p></div><Link className="text-link" href="/properties">See all properties →</Link></div>
      {!catalog ? <Notice error title="Listings are temporarily unavailable"><p>We could not connect to the property service. You can still contact the team.</p><Link className="text-link" href="/contact">Contact Awaaz Estate</Link></Notice> : !catalog.data.length ? <Notice title="Our catalog is being prepared"><p>There are no published properties to show yet. Share your requirements and our team can follow up.</p><Link className="text-link" href="/contact">Tell us what you need</Link></Notice> : <div className="listing-grid">{catalog.data.map((property) => <ListingCard key={property.id} property={property} />)}</div>}
    </section>
    <section className="section container"><h2>From a search to a site visit</h2><div className="steps"><article><strong>01 · EXPLORE</strong><h3>Find your shortlist</h3><p>Filter by location, purpose and budget. Compare the facts that matter to you.</p></article><article><strong>02 · ASK</strong><h3>Get a clearer picture</h3><p>Send an inquiry or ask Awaaz about a listing. Our team can help confirm the details.</p></article><article><strong>03 · VISIT</strong><h3>See it in person</h3><p>Request a viewing. A request becomes an appointment once availability and the visit are confirmed.</p></article></div></section>
  </>;
}
