# Awaaz Estate public website

This is the public Next.js/TypeScript website. FastAPI owns property records and inquiry business logic. The existing `frontend/` remains the voice application. This project does not seed sample inventory or bypass staff authorization.

## Local development

Use Node 22, copy `.env.example` to `.env.local`, configure `AWAAZ_API_URL` and `SITE_URL`, then:

```sh
npm ci
npm run dev
```

Start FastAPI from the repository root with `python run.py`. This website listens on port 3000. The configured service city, area and contact details are optional; missing values produce explicit unconfigured states. Local direct Next access does not provide the existing assistant: the `/assistant/` path belongs to the parent reverse proxy. To use the voice app without that proxy, open its local FastAPI URL separately.

Checks:

```sh
npm run typecheck
npm run build
```

## API integration

- `GET /v1/public/listings` returns `{data, pagination: {page, page_size, total, total_pages}}`.
- `GET /v1/public/listings/{slug}` returns a `Listing` defined and checked at runtime in `lib/catalog.ts`.
- Filters: `q`, `transaction_type`, `property_type`, `city`, `area`, price/size ranges, bedrooms, repeated `amenities`, `sort`, `page`, `page_size`.
- Website `POST /api/inquiries` validates the request origin, request content and consent, then calls `POST /v1/public/inquiries`. Fields are `property_id?`, `request_type`, `client_name`, `contact_email?`, `contact_phone?`, `contact_preference`, `message`, `consent`, `consent_version`, and `idempotency_key`. At least one contact method matching the preference is required. The public reply contains no contact data.
- The form reports success only after the backend accepts the request; outages and unimplemented endpoints produce an error. An inquiry does not book or reserve a visit. Direct slot reservation awaits verified customer identity and the scheduling backend.
- Backend-approved photo URLs can be HTTPS derivative URLs or existing same-origin paths. This app does not invent or fetch arbitrary images server-side. Relative paths need an actual parent-owned proxy mapping; no media storage API is implemented here.

The website never sends admin/provider credentials to the browser. All API data calls are server-side and use `cache: no-store` to avoid stale availability. Availability on a page still needs reconfirmation before a transaction.

## Production topology

Build with `docker build -t awaaz-website .`; runtime is the standalone Next server, non-root, on `0.0.0.0:3000`. Pass `AWAAZ_API_URL`, `SITE_URL`, `SERVICE_CITY`, `SERVICE_AREA`, `CONTACT_EMAIL` and `CONTACT_PHONE` at runtime. The parent Compose/proxy owns HTTPS, `/assistant/`, `/v1/` and media routing. The website container must remain private: the gateway must overwrite `X-Forwarded-For` and `X-Request-ID` before Next, and FastAPI must trust only the gateway and website hops. The inquiry proxy forwards only those gateway headers for rate limiting/correlation, never browser Authorization headers. Do not expose this service directly to the internet under those forwarding assumptions.

## SEO and content

Public pages render real HTML and metadata on the server, with canonical URLs, robots and a current catalog sitemap. Filter variants and comparison/assistant/staff pages are noindex; robots allows crawling those pages so their noindex can be read. Area listing pages remain noindex until reviewed area guide content exists. Unconfigured service area is also noindex. Missing listing IDs return a genuine 404.

Listing data, photography, company identity, legal text, retention policy and active provider disclosures must be reviewed before business launch. Privacy and terms pages explicitly identify remaining operator information; they are not legal certification. Staff access is intentionally unavailable until backend authentication exists. Saved accounts/alerts, staff CRUD, maps, automated WhatsApp sending and direct slot reservations are separate backend features, not implemented by this public website.

The design uses a bright background, restrained green, large property photos where approved media exists, and readable filters. Missing photography is labeled. Fonts use Google Fonts with local serif/sans fallbacks; self-host approved font assets for deployments that require no external font requests. Keyboard focus, labels, responsive layouts and reduced motion are included; real-device accessibility and performance acceptance remain necessary.
