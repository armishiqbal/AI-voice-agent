# Project scripts

Command-line entry points live here. Application logic remains in `backend/app/` and
`services/tts/`; scripts parse command-line options, load project configuration, and call the
corresponding application services. Run them from the repository root.

```text
scripts/
├── admin/       # Explicit local administration, including Google OAuth consent
├── benchmark/   # TTS and document-chunk benchmarks
├── data/        # Inventory and knowledge-base ingestion
├── evaluation/  # Conversation, RAG, memory, appointment, and release reports
└── voice/       # Isolated speech-worker launcher
```

Examples:

```bash
python scripts/evaluation/evaluate.py
python scripts/evaluation/live_voice_latency.py --voice-mode hybrid --runs 7
python scripts/data/import_inventory.py ./inventory.csv --source crm-export-v1
python scripts/benchmark/benchmark_tts.py
```

The root-level `run.py` and `worker.py` remain stable launchers for the API and outbox worker.
