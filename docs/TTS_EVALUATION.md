# Optional local multilingual TTS: runtime and evaluation

For the capstone Fish/ElevenLabs comparison, see [comparison](FISH_ELEVENLABS_COMPARISON.md).
The browser also supports the configured OpenAI route; this document covers optional local workers.

The selected implementation candidate is a hybrid local model path behind the existing TTS
router. It is not yet a quality-approved model choice. The system must not claim support for a
language/script until native-speaker and latency gates below pass.

## Model and dependency boundary

- Indic Parler-TTS is the candidate for Urdu, English, Hindi, Bengali, and Punjabi. Its model
  card lists Urdu as supported, Punjabi as unofficial, and requires gated model access. At the
  reviewed Hugging Face revision `7b527af5ee8ed1f9a28d80b19703ed9bb8ba10ca`, the checkpoint
  file is 3.75 GB and the card identifies Apache-2.0 licensing. Roman Urdu/UrduLish must be
  evaluated separately; a general Urdu language label is not evidence of Roman-script quality.
- Chatterbox Multilingual V3 is the candidate for Arabic (and can cover English/Hindi if useful).
  Its official language list includes Arabic, English, and Hindi, but not Urdu, Punjabi, or
  Bengali. Its model card lists 0.5B parameters and MIT licensing. Do not route a language to it
  just because the model is described as multilingual.
- The Chatterbox worker pins upstream source commit
  [`5de7a54`](https://github.com/resemble-ai/chatterbox/tree/5de7a54aa4e5e2baadb0182dde554908b48b85c2)
  because PyPI `chatterbox-tts==0.1.7` hardcodes the Hub `main` branch and its `from_local`
  loader only selects the v2 checkpoint; this worker instead snapshots the pinned V3 model
  revision and loads it through that commit's explicit V3-aware local loader. That upstream
  commit declares `resemble-perth` from mutable `master`; the TTS project's uv override replaces
  it with Perth commit `ff1c8ac55a976971245cdd53c18d6131ca00d993`, which the lockfile records.
- Parler's runtime pins Transformers 4.46.1; Chatterbox currently pins Transformers 5.2.0.
  They must run in separate virtual environments and processes, not the backend environment.
- The existing MMS Urdu Latin checkpoint is not the commercial default: its model card states
  CC-BY-NC-4.0. Legal review is required before any commercial use.
- Model cards, libraries, voices, training data, and generated outputs can have different terms.
  Review the exact revision and all licenses before launch. Do not assume “open source” means
  unrestricted voice cloning or redistribution.
- Model metadata checked 2026-09-23: [Indic Parler-TTS model card](https://huggingface.co/ai4bharat/indic-parler-tts/tree/7b527af5ee8ed1f9a28d80b19703ed9bb8ba10ca)
  and [Chatterbox Multilingual model card](https://huggingface.co/ResembleAI/chatterbox). These
  are candidate metadata, not independent quality, commercial-legal, or runtime evidence.
- Worker defaults now pin Parler to `7b527af5ee8ed1f9a28d80b19703ed9bb8ba10ca`, its separate
  `google/flan-t5-large` description tokenizer to `0613663d0d48ea86ba8cb3d7a44f0f65dc596a2a`,
  and Chatterbox to `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`. Overrides must also be full
  40-character commit SHAs. Warmup and readiness report the selected revisions; downloads remain
  lazy and require explicit warmup.
- Do not download weights until launch languages/scripts, target hardware, cache location, and
  available disk headroom are approved. Warm and benchmark one worker at a time on constrained
  machines; the separate environments also consume storage beyond the model checkpoint itself.

## Install and run locally

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) first, then create and sync
independent environments; do not install the two extras into one environment. The lockfile
resolves the engine extras as mutually exclusive and replaces Chatterbox's mutable
`resemble-perth@master` requirement with a fixed source commit:

```bash
uv venv .venv-tts-parler
source .venv-tts-parler/bin/activate
uv sync --project services/tts --extra parler --locked --active
deactivate

uv venv .venv-tts-chatterbox
source .venv-tts-chatterbox/bin/activate
uv sync --project services/tts --extra chatterbox --locked --active
deactivate
```

If Parler access is gated, accept the model terms and provide an authorized `HF_TOKEN` only to
the Parler worker. Set `TTS_SERVICE_TOKEN` in the API `.env` and in both local service commands.
In `.env`, configure:

```dotenv
TTS_PROVIDER=opensource
TTS_PARLER_SERVICE_URL=http://127.0.0.1:8021
TTS_CHATTERBOX_SERVICE_URL=http://127.0.0.1:8022
TTS_SERVICE_TOKEN=replace-with-a-local-random-token
```

Run each model worker in a separate terminal. The processes start without model downloads;
then explicitly warm each model before enabling API traffic. Warmup downloads/loads its weights
and runs one smoke synthesis:

```bash
TTS_ENGINE=parler TTS_SERVICE_PORT=8021 TTS_SERVICE_TOKEN=replace-with-a-local-random-token TTS_MODEL_REVISION=7b527af5ee8ed1f9a28d80b19703ed9bb8ba10ca TTS_PARLER_DESCRIPTION_TOKENIZER_REVISION=0613663d0d48ea86ba8cb3d7a44f0f65dc596a2a .venv-tts-parler/bin/python scripts/voice/run_tts.py
TTS_ENGINE=chatterbox TTS_SERVICE_PORT=8022 TTS_SERVICE_TOKEN=replace-with-a-local-random-token TTS_MODEL_REVISION=5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18 .venv-tts-chatterbox/bin/python scripts/voice/run_tts.py
```

In separate terminals, warm the workers using their own environments:

```bash
TTS_ENGINE=parler TTS_SERVICE_TOKEN=replace-with-a-local-random-token .venv-tts-parler/bin/python -m services.tts.warmup
TTS_ENGINE=chatterbox TTS_SERVICE_TOKEN=replace-with-a-local-random-token .venv-tts-chatterbox/bin/python -m services.tts.warmup
```

`TTS_SERVICE_DEVICE=auto` selects CUDA, then Apple MPS, then CPU. Use a private service network
and HTTPS for remote workers. The worker requires `TTS_SERVICE_TOKEN` at startup in every
environment, including localhost; the API adapter, worker, launcher, and warmup command must
share that secret. It exposes
`GET /healthz`, authenticated `GET /readyz`, and authenticated `POST /v1/synthesize`; synthesis
returns mono PCM16 little-endian audio. Text is bounded, unsupported languages are rejected,
and concurrent synthesis is serialized per worker. Keep the model cache on storage with enough
space; downloads are intentionally not performed during API import or startup. `/readyz`
remains false until dependencies are present and authenticated warmup has loaded the model.

### Cancellation and bounded inference

The API cancels the HTTP response and stops yielding audio immediately when the caller
interrupts or disconnects. PyTorch generation currently runs in a worker thread and cannot be
forcibly stopped safely by cancelling its awaiting coroutine. The worker therefore holds its
single-inference lease until native generation really returns; this bounds memory and prevents
repeated barge-ins from stacking abandoned model threads. Compute can continue briefly after
playback has stopped, so record caller-perceived stop latency and backend inference-drain time
as separate measurements.

## Evaluation set and release gate

For each required language/script, prepare at least 30 short utterances and 10 longer utterances
covering greetings, property names, PKR amounts, dates/times, acronyms, questions, refusals,
code-switches, and long responses. Include separate slices for Urdu in Arabic script, Roman
Urdu, Urdu-English mixing, Arabic, Hindi, Punjabi, and Bengali. Use identical text wherever
candidate models overlap. Two native reviewers independently rate pronunciation, intelligibility,
naturalness, pacing, and consistent voice identity; adjudicate disagreements and retain only
consented evaluation audio.

Record model/revision, package lock, hardware/device, cold start, peak RAM/VRAM, time to first
audio, full response latency, P50/P95, jitter, failure rate, real-time factor, and behavior under
barge-in. Include concurrent-session and low-memory tests. The current models synthesize waveform
segments rather than token-level speech; chunking the HTTP response does not itself prove fast
time-to-first-audio or interrupting the underlying model computation.

Do not pass the TTS gate until every launch language/script meets the pre-approved human rubric,
the model terms are approved, resource budgets fit the target host, and live measurements meet
the latency SLO. If a language fails, keep it disabled or obtain explicit approval for a
different licensed model—never silently route it through an unvalidated voice.

### Run the local open-source evaluation

Create a JSON dataset containing owner/native-speaker-approved phrases. IDs become WAV file
names and must contain only letters, numbers, underscores, and hyphens. The benchmark checks
each worker's authenticated readiness response, queries its actual supported-language list,
records time to first audio, total generation latency, audio duration, real-time factor, and
failures, then saves synthesized WAVs and a blank two-reviewer scoring sheet. It labels sample
coverage separately from human quality; it never declares a model accepted.

Example dataset shape:

```json
{
  "version": "approved-phrases-v1",
  "cases": [
    {
      "id": "roman-urdu-greeting-short-001",
      "language": "ur-Latn",
      "category": "greeting",
      "length": "short",
      "text": "Assalam-o-Alaikum, aap kis shehar mein property dekh rahe hain?"
    }
  ]
}
```

Run only after the model worker has been installed and warmed. `--warmup` explicitly downloads
and loads the configured model; without that option, the script reports a not-warm worker instead
of initiating downloads.

```bash
python scripts/benchmark/benchmark_open_source_tts.py --dataset evals/tts_open_source.json --output-dir artifacts/tts-open-source --warmup
```

The output contains `report.json`, `human-review.csv`, and one WAV per synthesized case under
`audio/<engine>/`. Keep these artifacts in controlled storage and use only evaluation text/audio
approved for this purpose. A complete dataset must contain at least 30 short and 10 long phrases
per required language/script; absent or unsupported slices remain an explicit failed coverage
gate.

## External-provider comparison

`python scripts/benchmark/benchmark_tts.py` still measures Fish Audio versus ElevenLabs when their credentials are
available. Record first-audio and total latency, errors, encoding, pronunciation, code-switching,
naturalness, streaming, and cost. It is a separate commercial-provider comparison and does not
substitute for the open-source model evaluation above. Missing credentials produce error rows,
not synthetic scores or a winner.
