# Awaaz Estate marketplace website

<p align="center">
  <a href="https://github.com/haroonsh-dev"><img src="https://img.shields.io/badge/Architect-haroonsh--dev-18523c?style=for-the-badge&logo=github&logoColor=white" alt="haroonsh-dev" /></a>
  <img src="https://img.shields.io/badge/Next.js-15.5.24-black?style=for-the-badge&logo=next.js&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/React-19.3.0-61dafb?style=for-the-badge&logo=react&logoColor=black" alt="React 19" />
  <img src="https://img.shields.io/badge/TypeScript-5.7.3-3178c6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Design%20System-White--Glove%20SVG-0e3526?style=for-the-badge" alt="Design System" />
</p>

Next.js renders the public marketplace, location pages, account screens, agency workspace, and platform review screens. FastAPI remains the authority for public inventory, identity, permissions, inquiries, appointments, alerts, and media decisions. PostgreSQL is the production database; the existing Vite application remains the voice assistant at `/assistant/` behind the gateway.

## Local development

Use Node 22 and the Python environment documented in the repository. Configure the root `.env` for FastAPI, then:

```sh
python run.py
```

In a second terminal:

```sh
cd website
cp .env.example .env.local
npm ci
npm run dev
```

`AWAAZ_API_URL` points to FastAPI (default `http://127.0.0.1:8000`). Website checks:

```sh
npm run typecheck
npm run build
```

The existing voice app can be run with the repository's `frontend/` commands. The single-origin production gateway routes `/assistant/` and `/v1/` to FastAPI and the rest of the public site to Next.js.

## Implemented visitor and operator surfaces

- Public homepage, property search/details, city/area landing pages, shortlist, comparison, area guides, agent and agency directories, seller request, contact and legal pages.
- URL-based search filters with reviewed location suggestions, sorting, pagination, responsive list/map layout, and graceful list-only operation if MapTiler is not configured.
- Guest favorites and comparison; optional verified customer accounts for synchronized favorites/searches, consented daily email alerts, and owned viewing management.
- Agency submissions, availability and schedule management, inquiry follow-up, member views, and viewing changes. Agency submissions remain unpublished until Awaaz review.
- Platform review screens for organizations, revisions, media, reports, locations, and audit activity.
- Existing voice assistant integration. Voice, email, Calendar, authentication, public agency submissions, customer features, and map access remain controlled by their provider configuration and feature flags.

## API and security boundaries

The browser does not connect to PostgreSQL. Server pages and same-origin `/api/*` proxies call FastAPI with bounded payloads, same-origin mutation checks, request timeouts, and session CSRF tokens. Never place a service-role key, staff token, SMTP credential, or API secret in a `NEXT_PUBLIC_*` variable.

Public listing DTOs are filtered through the shared publication/media/organization rules; locations, maps, agency profiles, assistant recommendations, and reservations use corresponding public visibility and eligibility checks. Coordinates are exposed only after review. Private originals and review evidence are not served as public media.

## Feature flags and providers

Keep these disabled until their staging acceptance checks pass:

- `MARKETPLACE_ENABLED=false`: agency submission and organization-scoped catalog rules.
- `CUSTOMER_FEATURES_ENABLED=false`: account-owned data and daily alerts.
- `MAP_ENABLED=false` and `NEXT_PUBLIC_MAP_ENABLED=false`: viewport API and browser map. Configure a restricted MapTiler key before enabling.
- `ASSISTANT_CONCIERGE_ENABLED=false`: website concierge rollout. The API and voice-provider readiness still determine whether assistant actions are available.

For authenticated workspaces, configure Supabase email auth in both server and browser settings, enable authenticator MFA for staff/agency users, and use asymmetric RS256/ES256 signing so FastAPI can validate JWTs through the provider JWKS. Configure `SUPABASE_URL` and `SUPABASE_ANON_KEY`; configure `SUPABASE_SERVICE_ROLE_KEY` only on the backend for storage operations. Create and lock down the private original/processed buckets and public derivatives bucket according to the storage policy in the operational runbook. Set a persistent `PII_ENCRYPTION_KEY` before accepting customer records.

Set real `CONTACT_EMAIL`, `CONTACT_PHONE`, and `CONTACT_WHATSAPP` values only after the company approves them. Configure SMTP and sender identity for OTP and alerts, and Calendar/CRM delivery only when provider receipts can be monitored. An API-accepted reservation or inquiry is not proof that an external provider delivered it.

## Database and controlled browser fixtures

Use additive migrations and take a backup before production migration:

```sh
alembic -c backend/alembic.ini upgrade head
```

Production requires PostgreSQL. SQLite is for local development and fast tests; it does not prove PostgreSQL locking, uniqueness, or booking race behavior. Do not import demonstration inventory into production. The controlled marketplace browser fixture is an isolated test-only FastAPI module and refuses database paths outside `/tmp/awaaz-browser-*`; its source marker is excluded in production.

## Staging acceptance and rollback

Before turning on the public marketplace, verify with actual agency-owned inventory and provider accounts:

1. Back up and migrate PostgreSQL; verify IDs, appointment history, and outbox receipts remain intact.
2. Confirm Supabase email verification, MFA enforcement, session revocation, CSRF, and cross-organization denial.
3. Verify media size/type limits, metadata stripping, private review and public approval flow.
4. Walk search → listing → inquiry and verified viewing end to end. Confirm an agency receives the request, competing slot requests produce one reservation, and external delivery status matches provider receipts.
5. Verify stale inventory is excluded from reservation, assistant results and alerts; test unsubscribe while a notification is queued.
6. Test map key restrictions/fallback, keyboard/mobile layouts, canonical HTML, robots and sitemaps at 375, 768, 1024 and 1440 px.
7. Restore a backup and record actual PostgreSQL/provider/browser evidence before pilot.

Rollback by disabling marketplace/customer/map/assistant flags as appropriate, pausing outbound alerts and external submissions, and keeping authorized access to accepted viewing records. Do not delete authoritative listings, inquiries, appointments, or provider receipts as a rollback action. Public production deployment is not part of this implementation.

## SEO and content

Published listings, approved profiles, and reviewed guides render on the server with canonical URLs and structured data limited to supported facts. Search-filter permutations, account, assistant, and workspace screens are not added to the sitemap. Confirm listing title/price/location/date, agency coverage, photo rights, guide sources and legal/business content before indexing or launch. No fabricated listings, testimonials, ratings, sales counts, or verification claims should be used.
