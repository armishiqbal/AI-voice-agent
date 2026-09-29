# Fish Audio vs ElevenLabs — capstone comparison

Reviewed 2026-09-27 against current vendor documentation. This is a sourced capability
comparison and executable evaluation protocol. Vendor latency, language counts, naturalness,
and price statements are not independent results. No matched Fish/ElevenLabs live recordings
or human quality scores have been collected in this checkout.

| Dimension | Fish Audio | ElevenLabs | Project decision/evidence |
|---|---|---|---|
| Candidate | `s2.1-pro` is the configured API model; `s2.1-pro-free` is listed for development without TTFA or DPA guarantees | `eleven_v3_conversational` is the realtime expressive candidate; `eleven_flash_v2_5` is faster but its published 32-language list excludes Urdu | Record exact model + voice per run; candidate compatibility is not measured quality |
| Naturalness and Urdu pronunciation | Vendor lists broad multilingual support and a 13-language zero-shot cloning claim | v3/v3 Conversational publish 70+ languages including Urdu; Multilingual v2 and Flash v2.5 do not list Urdu | A listed language does not prove native Pakistani Urdu or UrduLish quality; native speakers must score matched phrases |
| Urdu-English switching | Needs mixed-script and Roman Urdu evaluation | Needs same matched evaluation | Include names, lakh/crore, street names, English technical terms |
| Latency and streaming | WebSocket and REST streaming; vendor describes sub-300 ms streaming | Vendor claims ~280 ms for v3 Conversational and ~75 ms for Flash v2.5; our adapter currently uses HTTP streaming | Vendor numbers exclude our full STT→agent→browser path. Measure end-of-speech→audible reply separately from TTS first byte |
| Voice cloning | Vendor offers instant cloning; paid plans claim commercial rights | Instant and Professional Voice Cloning; Professional cloning requires speaker verification and Creator plan or above | Use only a speaker who owns or has authorized the voice under both provider terms; verify exact plan and usage rights |
| Emotion | S2 voice-control tags support delivery direction | v3/v3 Conversational offer expressive audio tags | Restraint and natural timing need listening review; not enabled globally |
| Integration | Configured optional Fish API adapter | Optional ElevenLabs HTTP streaming adapter | Both use the common TTS router; Fish currently returned HTTP 402 and ElevenLabs has no configured key |
| Robustness | Catch errors, bounded stream | Catch HTTP errors, timeout | Benchmark records failures; unavailable credentials do not count as a pass |

The live request contract initially omitted Fish's required model-selection header, so the
configured model was not actually selected. The adapter now sends that header and the
provider-supported MP3 sample rate. A one-phrase `s2.1-pro-free` smoke then returned 43,466
bytes, with 909 ms to first audio and 1,805 ms total; this single generated phrase is TTS-only
and was not human-scored. The normal paid `s2.1-pro` configuration previously returned HTTP
402. ElevenLabs returned `ELEVENLABS_API_KEY is not configured`. See
`artifacts/evaluation/fish-free-model-smoke-2026-09-27.json`.

Fish currently lists `s2.1-pro` as its recommended production model and `s2.1-pro-free` at $0
for testing, prototyping, development, and smaller businesses, without TTFA or DPA guarantees.
Its paid API uses usage-based billing and supports WebSocket/REST streaming. Vendor language
and cloning claims do not establish UrduLish quality or commercial suitability for this client.
[Fish model overview](https://docs.fish.audio/overview/capabilities),
[Fish pricing and rate limits](https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits),
[Fish voice cloning](https://fish.audio/voice-clone/).

ElevenLabs distinguishes expressive v3/v3 Conversational, Multilingual v2, and low-latency
Flash v2.5. Current published model descriptions list Urdu for v3 families but not for
Multilingual v2 or Flash v2.5. Its latency estimates are vendor measurements, not this
application's results. [ElevenLabs models](https://elevenlabs.io/docs/overview/models),
[model selection](https://elevenlabs.io/docs/eleven-api/choosing-the-right-model),
[voice cloning and verification](https://elevenlabs.io/docs/eleven-api/concepts/voice-cloning).

## Cost model

Fish's current API rate table lists paid S2.1 Pro at **$15 per million UTF-8 bytes** and the
developer model at $0. Urdu-script text generally occupies more UTF-8 bytes than the same
approximate content in ASCII Roman Urdu; use actual serialized request bytes for costing.
[Fish API pricing](https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits).

ElevenLabs' current API page lists v3 at **$0.10 per 1,000 characters**, v3 Conversational at
**$0.05 per 1,000 characters**, Multilingual v2 at $0.10, and Flash/Turbo at $0.05. These are
published rates, not a quote for every account, voice, cloning option, or plan.
[ElevenLabs API pricing](https://elevenlabs.io/pricing/api).

For 1,000,000 ASCII characters (approximately 1,000,000 UTF-8 bytes before markup), these
rates yield about $15 Fish, $100 Eleven v3, or $50 Eleven v3 Conversational before other
charges. Mixed Urdu requires separate byte and character counts.
Add STT minutes, LLM tokens, telephone minutes, storage, retries, infrastructure, taxes, and plan
minimums before comparing total call cost. Do not compare free development allowances as an SLA.

## Reproduce the experiment

Configure the two providers in ignored `.env`; install `voice-fish,voice-elevenlabs`. Run:

```bash
python scripts/benchmark/benchmark_tts.py --audio-dir artifacts/tts-review > artifacts/tts-comparison.json
```

Create `artifacts/` first if absent. The 20 phrase corpus covers UrduLish, Urdu script, English,
numbers, bookings, and additional languages. Run three warm and three cold repetitions on the
same host/network. Preserve model IDs, voice IDs (no keys), timestamp, provider region, and billed
units. The script saves completed MPEG recordings only and caps each recording at 10 MB.

Randomize file names into blinded A/B review copies. At least two native Urdu speakers score 1–5
for naturalness, pronunciation, switching, intelligibility, emotion restraint, and consistency.
Track missing/failed samples in the denominator. Record cloning similarity only for an authorized
reference speaker. Use `HUMAN_VOICE_RUBRIC.md`; annotate disagreements rather than invent an average.
Test interruption and streaming continuity in the actual browser separately from downloaded clips.

Decision gate: choose only after required quality thresholds, acceptable failure rate, and measured
latency/cost pass. Current selection remains provisional; provider keys and human reviews are missing.
