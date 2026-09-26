# Ten-minute end-to-end demonstration

Use the [offline slide deck](DEMO_SLIDES.html). Start API and worker with [operations](OPERATIONS.md).
Before presenting, confirm real inventory, selected speech readiness and authorized test-account
Google/n8n/Twilio setup. Never send messages to real clients as a demo. If a prerequisite is
missing, identify the blocked step and show its implementation; do not replace it with a fake
receipt or pretend browser audio is an incoming telephone call. Keep all secrets off-screen.

## 00:00–00:45 · 45 seconds — The problem and the promise

Introduce the business problem: missed calls, inconsistent answers and manual coordination. State that the local implementation is delivered and actual deployment is deferred. Explain that today’s live steps depend on configured real company data and test accounts.

## 00:45–01:45 · 60 seconds — Architecture

Explain why SQL decides availability and the model phrases an answer. Describe OpenAI/Deepgram speech options and selected TTS. LangGraph chooses typed routes; trusted services execute actions. Show ARCHITECTURE.md if the audience wants the full diagram.

## 01:45–03:15 · 90 seconds — Incoming call and natural turns

Use an actual incoming phone call only with configured Twilio and public TLS. Otherwise explicitly show browser voice and state carrier acceptance is pending. Show three continuous turns, preserved budget and one interruption. Do not pretend a recording or text response is live voice.

## 03:15–04:15 · 60 seconds — Facts before persuasion

Show selected SQL facts and a matching brochure/FAQ source. Ask whether a cheaper option is available. If inventory is empty, show the honest no-match response and explain the required import. Never silently replace company data with fixtures.

## 04:15–05:00 · 45 seconds — Safety and uncertainty

Demonstrate one injection and an unknown-detail question. Explain that finite tests do not prove universal security. Point to consent, source validation, availability checks and employee mapping as deterministic controls.

## 05:00–06:15 · 75 seconds — Book a visit

Use a test account and a real reviewed property. Speak the desired appointment, confirm details, then show the stored reference. A pending outbox event means delivery is pending; do not announce a Calendar or email success prematurely.

## 06:15–07:15 · 60 seconds — Calendar, employee email, CRM

With operator credentials, show the actual event, message and committed CRM receipt. Without them, show the implemented adapters/export and blocked readiness labels. Explain retry leases, recorded receipts and the remaining ambiguous-send crash window.

## 07:15–08:15 · 60 seconds — Reschedule and cancel

Use the same appointment reference and consented matching email. Verify the changed time remotely, then cancel. If external services are unavailable, demonstrate deterministic local lifecycle and label remote steps pending; do not claim external success.

## 08:15–09:15 · 60 seconds — Evidence, not assumptions

Show the latest generated evaluation output including failed/skipped cases and sample sizes. Explain that SQL fixture scores are not live company-vector accuracy, and node timing is not end-to-end voice latency. Open the human rubric with genuine reviewer results only.

## 09:15–10:00 · 45 seconds — Handover and next gate

Close with the requirement matrix, operations guide, maintenance plan and Docker/Compose preparation. Name each unresolved prerequisite plainly. Summarize future WhatsApp/SMS, CRM and validated multilingual work without calling those features implemented.
