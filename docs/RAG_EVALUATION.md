# RAG and property intelligence evaluation

SQL is authoritative for listing price, availability, size and assigned employee. The vector store supplies brochure and descriptive context only after the SQL property filter. Both Pinecone and local FAISS are supported; FAISS uses the configured real OpenAI embedding provider at runtime. Local adapter tests use explicitly deterministic test embeddings.

## Executed chunk-size experiment

Run:

```bash
python scripts/benchmark/benchmark_chunk_retrieval.py --output artifacts/evaluation/chunk-retrieval.json
```

This compares six character-based segmentation configurations on ten **synthetic** handbook documents and twenty manually paired gold-source questions. The corpus and gold evidence sentences are in `backend/app/evaluation/chunks.py`. It is not company data. Ranking uses local token frequency and inverse document frequency, with length normalization; no embedding service, LLM, or external API is called.

Metrics:

- Source accuracy@1: first retrieved chunk belongs to the gold document.
- Source recall@3: at least one of the top three chunks belongs to that document.
- Complete evidence recall@3: at least one top-three chunk contains the whole gold support sentence. This exposes boundaries that retrieve the correct document but cut the supporting fact.

| Characters | Overlap | Chunks | Source accuracy@1 | Source recall@3 | Complete evidence recall@3 |
| --- | --- | --- | --- | --- | --- |
| 128 | 0 | 50 | 95% | 95% | 45% |
| 128 | 32 | 60 | 95% | 95% | 70% |
| 256 | 0 | 30 | 95% | 95% | 45% |
| 256 | 64 | 30 | 95% | 95% | 95% |
| 512 | 0 | 20 | 95% | 95% | 95% |
| 512 | 128 | 20 | 95% | 95% | 95% |

On this corpus, 256/64 is the smallest tested window preserving complete evidence for every lexical hit. The default ingestion setting is deliberately unchanged: this small synthetic experiment does not establish the best configuration for client brochures. The paraphrase “Are profits assured?” misses the source saying returns are never guaranteed, exposing the lexical baseline's semantic limitation. Repeat against actual approved company documents and real embeddings before selecting a deployment configuration.

## Executed real-embedding FAISS comparison

Run (uses configured OpenAI credentials; sends only the synthetic corpus to the embedding API):

```bash
python scripts/benchmark/benchmark_chunk_retrieval.py --live-embeddings --output artifacts/evaluation/chunk-retrieval-live-embeddings.json
```

A local run completed with real `text-embedding-3-small` embeddings and transient FAISS cosine-similarity indexes. The 20 queries are embedded once and each chunk configuration is embedded in one batch (seven requests total). Production knowledge indexes are never opened or changed. No mock fallback is used when the provider is unavailable.

| Characters | Overlap | Source accuracy@1 | Source recall@3 | Complete evidence recall@3 |
| --- | --- | --- | --- | --- |
| 128 | 0 | 100% | 100% | 50% |
| 128 | 32 | 100% | 100% | 75% |
| 256 | 0 | 95% | 100% | 50% |
| 256 | 64 | 95% | 100% | 100% |
| 512 | 0 | 95% | 100% | 100% |
| 512 | 128 | 95% | 100% | 100% |

Real embeddings retrieved the gold source for the lexical paraphrase miss. Overlap improved support-sentence retention even where source recall was already perfect. These scores demonstrate actual embedding/vector retrieval on a deliberately small synthetic corpus; they do not measure answer generation, company-document accuracy, Urdu fluency, or live voice latency. The model and corpus are recorded in the generated report.

## Other reproducible evidence

`python scripts/evaluation/evaluate_rag.py` runs the twenty-case SQL fixture baseline and reports exact-match retrieval accuracy, SQL-grounded property-reference rate, and unexpected property-ID case rate, with denominators. The grounding and hallucination metrics are scoped to property references; they are **not** vector retrieval scores or free-form factual-claim entailment scores.

`python scripts/evaluation/evaluate_conversations.py --output artifacts/evaluation/multiturn-conversations.json` runs 44 isolated conversations / 92 turns across eleven required categories. It checks routing, preference memory and available property IDs. It does not measure live voice, model semantic quality, Calendar delivery or email delivery. Existing synthetic rental inventory uses a deliberately artificial price ladder; these numbers are not market estimates.

## Runtime grounding and remaining evaluation

- Structured model prompts include SQL listing facts and retrieved source text.
- Returned listing IDs and source IDs are checked; invalid or missing citations trigger deterministic fallback.
- Vector results are checked again against the SQL-selected property IDs.
- The graph rechecks availability immediately before returning a decision.
- SQL fallback remains available when vector retrieval fails.
- Citation presence does not prove every generated sentence is entailed. A human or separate entailment evaluation must check arbitrary model prose.
- Refresh/version policy must be operated explicitly: the adapters upsert source IDs; they do not automatically discover and delete superseded brochures under different IDs.

Still required for client-data evidence: gold-source retrieval with real embeddings, Urdu and Roman Urdu paraphrases, contradictory document versions, no-answer questions, factual-claim annotation, and retrieval latency percentiles. No score in this document substitutes for those checks.
