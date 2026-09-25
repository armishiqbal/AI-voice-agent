# RAG and property intelligence evaluation

SQL is the source of truth for price, availability, size, employee, and appointment facts.
Pinecone is evaluated only for brochure, FAQ, payment-plan, and descriptive context.

## Retrieval set

Create twenty questions with gold source IDs, including city/purpose filters, payment plans,
amenities, unavailable inventory, conflicting brochure versions, Urdu script, Roman Urdu, and
unknown questions. For each question record the SQL filter, expected property IDs, expected source
IDs, and whether clarification or handoff is correct.

## Metrics and failure rules

- Retrieval accuracy: source recall@k and property precision@k.
- Hallucination rate: percentage of cases where returned property IDs are outside the gold set.
- Grounded answer rate: every factual claim has a gold source or SQL fact.
- Miss behavior: no-result questions must not receive an invented answer.
- Factual property answers may be phrased by the structured model only when the selected property
  and returned source IDs remain inside the SQL-selected/RAG-filtered evidence set; invalid model
  IDs fall back to the deterministic SQL answer.
- Version behavior: newer source versions supersede older chunks.
- Latency: filtered retrieval P50/P95 and embedding/provider errors.

Run `python scripts/benchmark/benchmark_chunks.py <document> --source <version>` before ingestion and keep the
chosen chunk size with the evaluation report. The local fixture evaluation is separate from live
Pinecone evidence.

`python scripts/evaluation/evaluate_rag.py` runs the twenty-case SQL-grounded baseline and explicitly reports
`pinecone_evidence: false`; it must not be reported as a live vector-retrieval score.
