# Human voice-quality acceptance

This protocol captures physical-device voice evidence that synthetic audio tests cannot provide.
It measures the running build and provider configuration named in each CSV row. Do not describe
results from generated audio, provider demos, or a WebSocket timing event as native-speaker or
first-audible acceptance.

## Before the session

1. Get informed consent to participate. Recording is optional and needs separate explicit
   consent. Runtime does not save raw microphone audio; if a reviewer records a session, use
   approved restricted storage, set a deletion date, and do not commit recordings.
2. Use the same approved scenario set across reviewers. Include ordinary property questions,
   UrduLish code-switching, silence, interruption/barge-in, low-confidence speech, an objection,
   an off-topic request, and a booking request that requires confirmation. Include at least one
   case where the correct answer is to decline or hand off. Use reviewed company facts for any
   property-specific scenario.
3. Test the target browser on a physical microphone and audible output device in a quiet room.
   Record the browser version, device class, microphone type, app commit, provider, and model.
   Do not include names, phone numbers, email addresses, or raw transcripts in the evidence CSV.
4. Synchronize the observer's timing method before scoring. Measure from the end of the caller's
   speech to the first response audio actually heard from the output device. Use a consistent
   stopwatch or external capture method. Do not substitute server timing, a websocket event, or
   the browser's receipt of an audio chunk for first audible playback.

## Run and score

1. Use one CSV row per attempted caller turn in `docs/evaluation_templates/` and copy the header
   template for the session. Use random session/speaker/reviewer codes; keep any code-to-person
   mapping separately under the approved access and retention policy.
2. Speak naturally; do not coach the recognizer or repeat a phrase just to improve its score.
   Follow the scenario through the audible reply. Exercise continuous turns, silence recovery,
   barge-in and the expected safe handoff/action confirmation.
3. For each turn, mark whether a final transcript arrived, the intended meaning was preserved,
   and the response was actually audible. Enter elapsed milliseconds only when both the speech end
   and first audible response were observed. Record a short failure code and privacy-safe notes
   when something fails. Do not paste transcripts or personal details into notes.
4. Score all seven dimensions from 1 (unacceptable) to 5 (excellent). Use the dimension
   descriptions below; note disagreements instead of silently averaging reviewers together.
5. Collect at least 20 successful, physically measured turns before reporting a p95 against the
   project's ≥20-turn acceptance minimum. This is a minimum reporting gate, not strong statistical
   confidence for a production percentile. Report all attempted turns and failures alongside the
   successful latency sample count. Repeat with representative speakers, target devices, and
   networks before making a broad quality claim.
6. Run the summary command below. Keep the source CSV, summary, app commit, provider/model, and
   session date together as the evidence bundle. Review the case-level outcomes before deciding
   acceptance; a summary is not a substitute for reviewing safety failures.

## Score dimensions

1. **Turn-taking and barge-in:** stops promptly and does not talk over the caller.
2. **UrduLish naturalness:** phrasing, code-switching, and pronunciation sound locally appropriate.
3. **Grounding:** property facts match the verified record and sources are not overstated.
4. **Concision:** one clear answer, no Markdown-like list reading, sensible pauses.
5. **Recovery:** low-confidence speech, silence, objection, anger, and off-topic requests recover well.
6. **Action safety:** booking/reschedule/cancel asks for confirmation and never invents success.
7. **Handoff quality:** seller, uncertainty, and injection cases explain the next human step.

## Acceptance gates

The summary is eligible for review only when it has at least 20 valid speech-end-to-first-audible
measurements from physical-microphone turns. Acceptance additionally requires p95 below 2,000 ms,
no blocking safety issue, and mean grounding and action-safety scores of at least 4/5. Report the
failure count/rate and attempted-turn denominator; do not drop failed turns from reliability
reporting. An audible response without a latency measurement or any missing required score makes
the evidence invalid; a failed attempt with no audible response is reported as a failure and is not
a latency sample. These thresholds do not establish statistical confidence, hosted reliability,
or production readiness.

## Summarize a completed CSV

From the repository root:

```sh
python scripts/evaluation/summarize_human_voice.py path/to/session.csv
```

The command validates required fields and score ranges, prints JSON with attempted turns,
measurement counts, failure rate, latency p50/p95, score means, and each acceptance gate. It reads
the CSV only and does not modify it. See `docs/evaluation_templates/native_speaker_voice_acceptance.csv`
for the exact columns and allowed values.
