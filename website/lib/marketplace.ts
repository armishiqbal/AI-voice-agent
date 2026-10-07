import { apiJson, CatalogError } from "./catalog";
import { FALLBACK_AGENCIES, FALLBACK_AGENTS, FALLBACK_GUIDE_SUMMARIES } from "./fallbackData";

export type Agency = {
  id: string;
  slug: string;
  name: string;
  description: string;
  coverage: string[];
  contact_email: string | null;
  contact_phone: string | null;
  approved_at: string | null;
  address?: string;
  established?: string;
  license_number?: string;
  whatsapp?: string;
};

export type Agent = {
  slug: string;
  name: string;
  languages: string[];
  agency: Agency;
  title?: string;
  bio?: string;
  specialties?: string[];
  phone?: string;
  email?: string;
  whatsapp?: string;
  experience_years?: number;
  license_id?: string;
};

export type GuideSummary = {
  city_slug: string;
  area_slug: string;
  title: string;
  reviewed_at: string | null;
};

export const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;

function validAgency(v: unknown): v is Agency {
  return (
    isObject(v) &&
    ["id", "slug", "name", "description"].every((k) => typeof v[k] === "string") &&
    Array.isArray(v.coverage) &&
    v.coverage.every((c) => typeof c === "string")
  );
}

export async function agencies(): Promise<Agency[]> {
  try {
    const r = await apiJson("/v1/public/agencies");
    if (!isObject(r) || !Array.isArray(r.data) || !r.data.every(validAgency)) {
      return FALLBACK_AGENCIES;
    }
    const mapped = (r.data.length > 0 ? r.data : FALLBACK_AGENCIES).map((org) => {
      const fallback = FALLBACK_AGENCIES.find((fa) => fa.slug === org.slug || fa.id === org.id);
      return {
        ...org,
        address: typeof (org as Agency).address === "string" ? (org as Agency).address : fallback?.address,
        established: typeof (org as Agency).established === "string" ? (org as Agency).established : fallback?.established,
        license_number: typeof (org as Agency).license_number === "string" ? (org as Agency).license_number : fallback?.license_number,
        whatsapp: typeof (org as Agency).whatsapp === "string" ? (org as Agency).whatsapp : fallback?.whatsapp,
      };
    });
    return mapped;
  } catch {
    return FALLBACK_AGENCIES;
  }
}

export async function agents(): Promise<Agent[]> {
  try {
    const r = await apiJson("/v1/public/agents");
    if (!isObject(r) || !Array.isArray(r.data)) return FALLBACK_AGENTS;
    const mapped: Agent[] = r.data
      .map((v): Agent | null => {
        if (
          !isObject(v) ||
          typeof v.slug !== "string" ||
          typeof v.name !== "string" ||
          !Array.isArray(v.languages) ||
          !v.languages.every((l) => typeof l === "string") ||
          !validAgency(v.agency)
        ) {
          return null;
        }
        const fallback = FALLBACK_AGENTS.find((fa) => fa.slug === v.slug);
        return {
          slug: v.slug,
          name: v.name,
          languages: v.languages,
          agency: v.agency,
          title: typeof v.title === "string" ? v.title : fallback?.title,
          bio: typeof v.bio === "string" ? v.bio : fallback?.bio,
          specialties: Array.isArray(v.specialties) ? (v.specialties as string[]) : fallback?.specialties,
          phone: typeof v.phone === "string" ? v.phone : fallback?.phone,
          email: typeof v.email === "string" ? v.email : fallback?.email,
          whatsapp: typeof v.whatsapp === "string" ? v.whatsapp : fallback?.whatsapp,
          experience_years: typeof v.experience_years === "number" ? v.experience_years : fallback?.experience_years,
          license_id: typeof v.license_id === "string" ? v.license_id : fallback?.license_id,
        };
      })
      .filter((a): a is Agent => a !== null);

    return mapped.length > 0 ? mapped : FALLBACK_AGENTS;
  } catch {
    return FALLBACK_AGENTS;
  }
}

export async function guides(): Promise<GuideSummary[]> {
  try {
    const r = await apiJson("/v1/public/areas");
    if (!isObject(r) || !Array.isArray(r.data)) return FALLBACK_GUIDE_SUMMARIES;
    const mapped = r.data
      .map((v) => {
        if (!isObject(v) || !["city_slug", "area_slug", "title"].every((k) => typeof v[k] === "string")) {
          return null;
        }
        return {
          city_slug: String(v.city_slug),
          area_slug: String(v.area_slug),
          title: String(v.title),
          reviewed_at: typeof v.reviewed_at === "string" ? v.reviewed_at : null,
        };
      })
      .filter((g): g is GuideSummary => g !== null);

    return mapped.length > 0 ? mapped : FALLBACK_GUIDE_SUMMARIES;
  } catch {
    return FALLBACK_GUIDE_SUMMARIES;
  }
}
