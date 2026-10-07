# Awaaz Estate: professional website improvement plan

Review date: 4 October 2026. Reviewed against the running website at `http://localhost:3000/` and the current local working tree, which contains changes made after commit `a95a6ea`.

## Product objective

A visitor should be able to identify suitable properties, understand the asking price and property facts, assess what the company has actually checked, and contact an accountable person or reserve a viewing. The website should support that journey through ordinary controls, with voice as an additional way to search and ask questions.

Keep the existing warm background, forest-green actions, serif headings, and company-catalog model. Improve the information and interaction design within the current Next.js/FastAPI architecture. Islamabad and Rawalpindi are the current local presentation; the operator must confirm the actual service area before launch.

## Evidence from the current website

| Priority | Finding | Observed evidence | Required outcome |
| --- | --- | --- | --- |
| P0 | Verification claims contradict the record | The F-7 listing shows `Status: not reviewed`, followed by text saying ownership documents and non-encumbrance certificates have been verified by an in-house legal team. Its price area also says all dues are verified. | Every public review statement must come from a specific approved review record. Unknown checks must remain unknown. |
| P0 | Development content is presented as actual inventory | `backend/seed_dev_data.py` supplies the displayed property titles, legal descriptions, coordinates, and Unsplash photos. | Clearly label demonstration content and isolate it from publishable company inventory. Real listings require permitted photos of the actual property and approved facts. |
| P0 | Trust metrics and reviews lack visible provenance | `MarketMetricsBar` hardcodes 100%, Rs. 4.8B+, and voice latency below 1.2s. `ClientTestimonials` hardcodes named customers and five-star quotes; `NeighborhoodExplorer` hardcodes counts such as 34+ listings. | Remove unsupported claims or replace them with approved, dated records and correctly defined metrics. |
| P1 | Sorting drops location filters | Starting at `/properties?area=f-7`, choosing price low to high navigated to `/properties?sort=price_asc`; the result count changed from one to six. | Sorting must preserve city, area, transaction, category, price, size, bedrooms, and amenities. |
| P1 | Neighborhood navigation does not reliably match inventory | Clicking the DHA neighborhood card opened `area=dha-phase-2` and returned zero results, despite a DHA Phase 2 listing on the homepage. | Use an authoritative location identifier or a consistent slug-to-location resolver. |
| P1 | Mobile search starts too far down the page | At a 375px-wide viewport, the header wraps onto a second row and the search submit action is below the first screen. | Give search a compact, clear entry point with a usable mobile navigation menu. |
| P1 | Results and detail information need property-specific treatment | Cards show rental prices without a period, commercial listings show zero bedrooms, and the F-7 sale villa recommends rental apartments and an office as similar properties. | Use transaction/category-specific facts, price labels, and recommendations. |
| P2 | Voice demonstration is visually described as active intelligence | `VoicePlaygroundWidget` switches between predefined replies and property references while showing “Neural Voice Active” and “Verified Inventory RAG”. | Label examples as demonstrations. Show live readiness only when supplied by the working voice service. |

Scope of this review: homepage at desktop and 375px mobile widths, neighborhood navigation, catalog filtering/sorting, one property detail page, and relevant source files. No real email/OTP submission, microphone session, production performance measurement, or full security audit was performed.

## 1. Correct credibility and publishing controls first — P0

Create a public claim inventory covering homepage, cards, property details, area guides, about page, privacy copy, and footer. For each claim, record its source, scope, reviewer, approval date, and expiry where appropriate.

- Replace blanket “CDA / RDA verified” labels with the actual review scope, such as availability confirmed or an approval document reviewed. A generic verification status must not be translated into an authority-specific legal claim.
- Show availability confirmation and document-review dates separately. A recent availability check does not establish ownership, dues clearance, or planning approval.
- Hide testimonials until the company supplies genuine feedback, permission to publish it, and approved attribution. Do not populate the empty state with named fictional customers.
- Remove catalog-value and latency figures until they are derived and measured correctly. Rental asking amounts must not be summed with sale asking prices as a catalog asset value.
- Replace hardcoded neighborhood counts with counts from the same eligible inventory used by results. Label any price statistics as asking-price statistics, with transaction/category, sample size, and date range; suppress insufficient samples.
- Mark development fixtures and illustrative media visibly. Prevent the development seed command from writing to a production database. Production publication must reject demonstration records, incomplete classification, missing permissions, and unapproved photos.
- Replace promises such as universal escrow, certified agents, zero encumbrances, and a 24-hour response with business-approved service descriptions. Show an operating commitment only after staff and process coverage exist.
- Keep technical implementation claims out of customer copy unless they help a customer. In particular, review the public encryption wording against the actual implementation and published privacy policy.

Acceptance: a property whose review status is not reviewed displays no positive legal-review claim anywhere. Every testimonial and numerical marketing claim has traceable evidence. Production cannot publish demonstration inventory.

## 2. Simplify the homepage around discovery — P1

Recommended page order:

1. Compact header: logo, Properties, Areas, About, Contact, and Shortlist. Keep voice available as a secondary action. On mobile use a menu with a clear focus-managed open/close state.
2. Hero and search: plain location-specific headline, one supporting sentence, Buy/Rent, location, category, budget, and Search. Suggested headline: “Find your next property in Islamabad & Rawalpindi.” Use company-approved coverage.
3. Actual available properties: show a useful small selection and an obvious route to all results. Separate homes for sale and rentals when needed; commercial inventory gets an accurate category label.
4. Areas the company serves: real area photography or clearly identified illustrative media, actual inventory counts, and reviewed guides.
5. One concise “How it works” section: discover, ask/compare, arrange a visit. Combine the current repeated standards and guarantees sections.
6. A compact optional voice introduction with a clear live-launch action. Demonstrations must be visibly labeled.
7. Owner submission action, followed by the company footer and actual business contact details. Add genuine testimonials later when evidence exists.

Use the existing visual identity with smaller hero spacing and fewer competing badges, shadows, and animated status dots. Do not fill empty space with unrelated stock property photos. On desktop, approved local imagery can support a balanced hero; on mobile, prioritize the search entry and readable copy.

Acceptance: at 375px, visitors can identify where to search immediately without scrolling through a full block of marketing claims. Navigation has no accidental horizontal overflow. The main search and optional voice action have distinct visual priority.

## 3. Make search reliable and appropriate to local property buying — P1

Use the URL as the authoritative search state. Updating one control should update the relevant parameters and preserve the others. Reset pagination when filters change. Restore controls from the URL after refresh and browser back/forward navigation.

- Resolve city/sector/society/phase names through configured locations and approved aliases. Store/display readable names while querying a stable location identity. Include city in neighborhood links.
- Add location suggestions with keyboard selection. Distinguish city, sector, society, and phase so a broad society search does not falsely imply one specific phase.
- Use monthly PKR budget presets for rent and sale-price presets for buying in both the homepage and results. Preserve custom minimum/maximum amounts and validate ranges.
- Provide separate city/area, category, bedroom minimum, size, and amenities controls. Surface advanced filters only when they add useful decisions.
- Use category-specific filters: bedrooms for homes; covered area and furnished status for apartments/offices where known; plot area and permitted-use information for plots where reviewed.
- Show active filter chips including location, result count, clear-all, and loading feedback. On mobile, use a filter drawer with an explicit Apply action and a visible filter count.
- Preserve approved parameters when switching sort or grid/list view. Do not let the results filter component silently rebuild a partial query.
- Explain empty states using the current criteria. Offer specific actions such as widening budget or clearing the area; do not silently change the search.

Acceptance: reproduce the F-7 sort case and confirm the area remains selected and the count remains one. The DHA card must find the existing eligible DHA listing. Rental budgets must be rental budgets. Refresh, back, pagination, and shared links must reproduce the same criteria.

## 4. Improve cards, shortlist, and comparison — P1

The first scan should reveal price, sale/rent, location, relevant size, category, and availability.

- Add “For sale” or “For rent” to every card. Rental prices must state `/month` or the stored rental period.
- Present one prominent readable PKR price. Use the full numerical amount as secondary detail or an accessible explanation when helpful.
- Use short factual titles; retain the full approved title on the detail page. Avoid stacking luxury adjectives.
- Show plot area and covered area separately when both are available. Support square feet, marla, and kanal using a documented local conversion, preserving the supplied unit and avoiding a universal conversion assumption.
- Suppress bedroom facts for offices/plots. Show relevant parking, floor, or frontage facts only when stored and approved.
- Render availability colors and wording from the real state. Sold, reserved, and needing-confirmation records must not use the same available-green indicator.
- Make Save and Compare actual stateful actions. Maintain a tray for up to three selected properties across browsing; the current single-property compare link should not discard previously selected properties.
- Explain that a guest shortlist is stored on the current device. Handle unavailable/archived saved listings without losing the rest of the shortlist.
- Provide a shareable detail link with accessible feedback when copied.

Acceptance: two properties can be added to comparison from separate result pages and compared together. Missing facts read “Not supplied” or are omitted according to context. A rental, plot, and commercial card each show appropriate facts.

## 5. Make detail pages support an informed decision — P1

Recommended sequence: summary and actions → actual photo gallery → property facts → description → amenities → scoped reviews → location/area information → related properties. Keep the contact/viewing panel available beside desktop content and as a compact bottom action bar on mobile.

- Use actual photographs of the listed property, approved alt text, a working gallery/lightbox, optional floor plan, and clearly labeled videos or tours. Never substitute unrelated interior imagery for missing photos.
- Provide a concise facts table with listing reference, transaction/category, supplied size measurements, rooms, parking, furnishing, possession/occupancy, and price/rental terms where the company has that information.
- Show the responsible company agent, profile, configured business phone/WhatsApp contact, and operating hours. Avoid exposing private staff identifiers or provider credentials through public DTOs.
- Give Ask a Question and Arrange a Viewing separate flows. A short inquiry should not require the visitor to start a booking.
- Display company service fees and the known scope of representation in reviewed business copy. Keep any cost calculator explicitly assumption-based; do not invent taxes, financing eligibility, or transaction charges.
- Replace generic travel times and nearby-school text with reviewed property/area information. Label route estimates and their origin/time assumptions if a routing service supplies them.
- Add a map only for approved public coordinates, labeling approximate positions clearly. Keep the address/list view useful when coordinates are absent.
- Recommend properties by compatible transaction, category, city/area, and reasonable budget range. If expanding criteria, explain that the suggestions are broader alternatives.

Acceptance: the F-7 villa page has no contradictory review copy or unrelated rental-office “similar” section. A buyer can answer what is being sold, where it is, the asking price, what was checked, and whom to contact.

## 6. Complete booking and lead handling as one recorded workflow — P1

Inspect and reuse the recently added viewing routes and `ViewingWidget` before changing them. Model the flow explicitly: choose slot → supply contact and consent → request email verification → verify → review the details → reserve → show reference and delivery state.

- Separate verification email delivery, verified contact, saved reservation, Calendar delivery, and appointment completion. Confirmation text must reflect the actual state.
- Require an explicit final reservation action after verified contact and reviewed details; avoid silently booking as soon as the OTP is accepted.
- Preserve entered data after recoverable errors. Refresh slots on a conflict and retain the chosen property and contact state where appropriate.
- Reuse identity-scoped idempotency and server-side employee resolution. Verify that contact changes invalidate the prior contact verification and that retries cannot create duplicate reservations.
- Keep debug OTPs and automatic development code filling out of production. Verify expiry, resend limits, attempt limits, and provider-outage behavior.
- Supply a protected management path for cancelling or changing a visit; knowing an email or reference must not authorize an action.
- Give inquiries a reference and an honest response expectation. Ensure staff can assign, acknowledge, record follow-up, and close with an outcome; notification failure must not lose the accepted inquiry.
- Give sellers a dedicated request category and form. Property submission remains a staff-reviewed request, not immediate publication.

Acceptance: a completed journey creates one reservation, an authorized staff member sees it, a conflict produces useful recovery, and delivery failure is shown as pending/failed delivery. A contact-button click alone never appears as an accepted inquiry.

## 7. Make voice useful within the property journey — P2

Retain the working voice pipeline and expose optional controls through the existing implementation. The current source contains several voice components, so first establish which surface is authoritative and remove duplicate integration paths only after verification.

- Pass selected-listing context by ID; resolve published facts on the server. Do not trust a browser-provided price, approval claim, or employee identity.
- Show actual readiness, microphone state, listening, reply, interruption, and recovery states.
- Keep samples clearly labeled and separate from current results. Sample replies should not claim that a legal approval has been checked.
- Permit manual search and contact to continue during a speech-provider outage.
- Return links to actual published matches. Voice booking must use the same verified-contact, availability, and authorization rules as the website.
- Measure voice response time through a documented method before displaying performance claims.

Acceptance: an unavailable speech provider produces a useful explanation and leaves manual actions usable. Demonstration text is never displayed as a completed live conversation.

## 8. Discovery, performance, and accessibility — P2

Build reviewed area pages using current coverage, actual inventory, useful local descriptions, dated sources, and approved public maps. Do not fabricate market-price trends or investment returns. Generate metadata for both Islamabad and Rawalpindi where relevant instead of always naming only Islamabad.

Index canonical listings and useful reviewed area pages. Keep private staff/customer pages and personal shortlist/comparison permutations out of indexing. Choose explicit crawl controls for arbitrary search combinations; canonical links alone are not a complete crawl-management strategy. Follow [Google's faceted-navigation guidance](https://developers.google.com/crawling/docs/faceted-navigation).

Optimize real image derivatives with responsive dimensions and modern formats, reserve image space, load lower-page images and maps lazily, and prioritize only the actual leading image. Consolidate repeated CSS and reusable components without rewriting the entire site. Measure the production build, rather than treating the current Next.js development server as performance evidence.

Target mobile LCP ≤2.5s, INP ≤200ms, and CLS ≤0.1 at the 75th percentile once sufficient real-user measurements exist. Keep laboratory results identified separately. These targets follow [Core Web Vitals thresholds](https://web.dev/articles/defining-core-web-vitals-thresholds).

Use [WCAG 2.2 AA](https://www.w3.org/WAI/WCAG22/quickref/) as the accessibility baseline: visible labels, accessible names, focus visibility, keyboard operation, contrast, error associations, and focus management in menus, filter drawers, galleries, and dialogs. Aim for 44px touch controls as a design target, respect reduced motion, and show the skip link when focused rather than as an accidental permanent layout row.

Acceptance: review 375, 768, 1024, and 1440px widths; complete search, comparison, inquiry, and viewing with a keyboard; document production-build measurements without claiming unmeasured field performance.

## 9. Operate the catalog and measure meaningful outcomes — P2

Prioritize staff work that keeps the public experience reliable: publication approval, assigned agent, availability reconfirmation, media permission, failed delivery handling, and an inquiry follow-up queue. Enforce record permissions and staff MFA through FastAPI, including direct API calls.

Record privacy-conscious events for search submission, no-result searches, listing views, shortlist/compare actions, accepted inquiries, saved reservations, delivered notifications, and completed/cancelled visits. Track inventory freshness, unassigned inquiries, overdue follow-ups, and delivery backlog. Keep contact details, OTPs, and conversation text out of analytics payloads.

Establish a baseline before choosing conversion targets. Test with buyers, renters, and an overseas representative using realistic tasks. Record whether they find a match, understand verification, and complete contact or booking without assistance. Do not infer sales from button clicks.

Acceptance: staff can explain and follow up every accepted request, stale inventory is surfaced, and dashboard events correspond to authoritative business records.

## Delivery order and release gates

| Increment | Work | Gate before moving on |
| --- | --- | --- |
| A — credible catalog | Demonstration isolation, claim cleanup, scoped reviews, real-photo publication controls | No unsupported public claims or publishable demo inventory |
| B — dependable search | URL state, authoritative locations, rental budgets, empty states, mobile filters | F-7 sorting and DHA navigation regressions resolved; back/refresh/share work |
| C — buyer decision flow | Compact homepage, category-aware cards, comparison tray, detail facts, accountable contact | Buyer and renter can find, understand, shortlist, compare, and inquire |
| D — recorded visits and operations | Verification/reservation states, conflict/retry handling, staff ownership and delivery visibility | One request creates one record; authorized staff can process it; outages are explicit |
| E — discovery and optimization | Reviewed guides, optional maps, voice context, SEO, performance, accessibility, analytics | Production/staging evidence recorded for the complete critical journeys |
| F — customer retention | Verified customer accounts, synchronized favorites, saved searches, opted-in daily alerts | Ownership, consent, unsubscribe, retention, and delivery deduplication verified |

The first implementation batch should be Increment A plus the two confirmed search regressions. Additional visual polish should follow those corrections. Expansion to external agencies or new regions remains dependent on reliable inventory and staff coverage.

## Handoff instructions for the implementing agent

Inspect the current working tree and preserve existing in-progress changes. Start with `website/app/page.tsx`, `website/components/MarketMetricsBar.tsx`, `ClientTestimonials.tsx`, `NeighborhoodExplorer.tsx`, `PropertyFilterBar.tsx`, `ListingCard.tsx`, `VoicePlaygroundWidget.tsx`, and `website/app/properties/[slug]/page.tsx`; inspect the current public/staff APIs and development seed process before changing data rules.

Keep FastAPI/PostgreSQL authoritative, public DTOs explicit, and existing IDs/history intact. Reuse current appointment and outbox services. Implement each increment with focused regression coverage and document its acceptance evidence. Obtain real company inventory/media, contact details, agent profiles, approved policy copy, service-fee wording, and provider configuration from the operator where required; missing business inputs should produce honest empty or unavailable states.

This document is a plan. The review did not change application code, publish inventory, send inquiries, reserve visits, or deploy the website.
