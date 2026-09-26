# Fish Audio vs ElevenLabs — capstone comparison

Reviewed 2026-09-26. This is a sourced capability comparison and executable evaluation protocol.
No comparative live recordings or human quality scores have been collected in this checkout.

| Dimension | Fish Audio | ElevenLabs | Project decision/evidence |
|---|---|---|---|
| Candidate | S2.1 Pro | Configurable Multilingual v2; evaluate v3/Flash separately | Record exact model + voice per run |
| Naturalness and Urdu pronunciation | Vendor lists broad multilingual support | Language coverage varies by model | Native Urdu reviewers must score our phrases; no winner inferred |
| Urdu-English switching | Needs mixed-script and Roman Urdu evaluation | Needs same matched evaluation | Include names, lakh/crore, street names, English technical terms |
| Latency | Streaming over WebSocket/REST | HTTP streaming in our adapter | Measure end-of-speech→audible reply separately from TTS first byte |
| Voice cloning | Reference voice support | Voice ID integration | Use only authorized voices; ownership/consent and plan permissions required |
| Emotion | Natural-language direction tags | Expressive models and audio tags vary by model | Restraint and natural timing need listening review; not enabled globally |
| Integration | Optional Fish SDK adapter | Optional HTTP streaming adapter | Both return compressed audio through common router |
| Robustness | Catch errors, bounded stream | Catch HTTP errors, timeout | Benchmark records failures; unavailable credentials do not count as a pass |

Fish lists S2.1 Pro as its recommended production model with 83 languages; the free developer
variant has different operational assurances. Language count does not establish UrduLish quality.
[Fish model documentation](https://docs.fish.audio/developer-guide/models-pricing/models-overview).

ElevenLabs distinguishes expressive v3, conversational v3, Multilingual v2, and low-latency Flash.
Its published latency estimates are vendor measurements, not this application's results.
[ElevenLabs models](https://elevenlabs.io/docs/overview/models).

## Cost model

Fish's detailed public table lists paid S2.1 Pro at **$15 per million UTF-8 bytes**. Marketing text
also says characters; use the detailed billing unit and confirm it on the account invoice.
Urdu script has more UTF-8 bytes than ASCII Roman Urdu. [Fish developer pricing](https://fish.audio/developers/).

ElevenLabs' API page lists v3 at **$0.10 per 1,000 characters** and v3 Conversational at
**$0.05 per 1,000 characters**. These are examples for those models, not a quote for the
configured Multilingual v2 voice, every plan, or cloning. [ElevenLabs API pricing](https://elevenlabs.io/pricing/api).

For 1,000,000 ASCII characters these example rates yield $15 Fish, $100 Eleven v3, or $50
Eleven v3 Conversational before other charges. Mixed Urdu requires separate byte/character counts.
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
