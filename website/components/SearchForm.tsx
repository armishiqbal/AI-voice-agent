import { scalar, type SearchParams } from "@/lib/catalog";

export function SearchForm({ params = {}, full = false }: { params?: SearchParams; full?: boolean }) {
  const amenities = (Array.isArray(params.amenities) ? params.amenities : params.amenities ? [params.amenities] : []).filter(Boolean);
  return <form action="/properties" method="get" className={`search-form ${full ? "filters" : ""}`}>
    <label>Location or keyword<input name="q" defaultValue={scalar(params.q)} placeholder="City, area or property" maxLength={100} /></label>
    <label>Looking to<select name="transaction_type" defaultValue={scalar(params.transaction_type)}><option value="">Buy or rent</option><option value="sale">Buy</option><option value="rent">Rent</option></select></label>
    <label>Property type<select name="property_type" defaultValue={scalar(params.property_type)}><option value="">All property types</option>{["house", "apartment", "plot", "shop", "office", "warehouse", "other"].map((type) => <option key={type} value={type}>{type[0].toUpperCase() + type.slice(1)}</option>)}</select></label>
    {full && <>
      <label>City<input name="city" defaultValue={scalar(params.city)} maxLength={64} placeholder="Any city" /></label>
      <label>Area<input name="area" defaultValue={scalar(params.area)} maxLength={128} placeholder="Any area" /></label>
      <label>Minimum price (PKR)<input name="min_price_pkr" type="number" min="0" step="1" defaultValue={scalar(params.min_price_pkr)} placeholder="No minimum" /></label>
      <label>Maximum price (PKR)<input name="max_price_pkr" type="number" min="0" step="1" defaultValue={scalar(params.max_price_pkr)} placeholder="No maximum" /></label>
      <label>Minimum size (sq ft)<input name="min_size_sqft" type="number" min="1" step="1" defaultValue={scalar(params.min_size_sqft)} placeholder="No minimum" /></label>
      <label>Maximum size (sq ft)<input name="max_size_sqft" type="number" min="1" step="1" defaultValue={scalar(params.max_size_sqft)} placeholder="No maximum" /></label>
      {[...amenities, ""].slice(0, 10).map((amenity, index) => <label key={index}>Amenity {index + 1}<input name="amenities" defaultValue={amenity} placeholder="For example, parking" maxLength={100} /></label>)}
      <label>Bedrooms<select name="bedrooms" defaultValue={scalar(params.bedrooms)}><option value="">Any</option>{[0, 1, 2, 3, 4, 5, 6].map((number) => <option key={number} value={number}>{number}</option>)}</select></label>
      <label>Sort by<select name="sort" defaultValue={scalar(params.sort) || "newest"}><option value="newest">Newest listings</option><option value="price_asc">Price: low to high</option><option value="price_desc">Price: high to low</option><option value="bedrooms_desc">Most bedrooms</option><option value="size_desc">Largest first</option></select></label>
    </>}
    <button className="button" type="submit">{full ? "Update results" : "Find a property"}</button>
  </form>;
}
