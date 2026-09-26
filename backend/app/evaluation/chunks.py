"""Offline chunk-size retrieval experiment; lexical scores are not embeddings."""
from __future__ import annotations

import math
import re
from collections import Counter

from app.services.ingestion import chunk_text

# Synthetic training material; none of these claims are company inventory facts.
FACTS = [
    ("parking", "Residents receive one reserved covered parking bay. Visitor vehicles use the outdoor guest lot.", ["Where do visitor vehicles park?", "How many covered parking bays does a resident receive?"]),
    ("security", "Security guards patrol the lobby every night. Entrance access requires a registered resident card.", ["What card is needed for entrance access?", "Who patrols the lobby at night?"]),
    ("school", "The nearby school provides primary classes. Families must confirm school admission eligibility directly.", ["Does the nearby school offer primary classes?", "Who confirms school admission eligibility?"]),
    ("hospital", "The community hospital operates an emergency department. Specialist clinic appointments require separate booking.", ["Is an emergency department available at the hospital?", "Do specialist clinic appointments need booking?"]),
    ("payment", "The reservation deposit is refundable only before agreement signing. Installment dates appear in the signed payment schedule.", ["When is the reservation deposit refundable?", "Where can installment dates be found?"]),
    ("maintenance", "Monthly maintenance covers common corridor cleaning. Repairs inside a private apartment are the owner's responsibility.", ["Does monthly maintenance cover corridor cleaning?", "Who pays for repairs inside a private apartment?"]),
    ("visit", "Property visits require an available employee and explicit customer confirmation. Bring identification to the reception desk.", ["What is needed before a property visit is confirmed?", "Where should visitors show identification?"]),
    ("cancellation", "Cancel a visit using its booking reference. The employee receives a cancellation notification after the calendar update.", ["What reference is needed to cancel a visit?", "When does the employee receive a cancellation notification?"]),
    ("developer", "Developer claims must be checked against official approval documents. Marketing brochures alone do not prove legal approval.", ["Which documents verify developer claims?", "Does a marketing brochure prove legal approval?"]),
    ("investment", "Rental income depends on vacancy and operating expenses. Capital appreciation is uncertain and returns are never guaranteed.", ["What expenses affect rental income?", "Are profits assured?"]),
]


def fixture_corpus() -> tuple[dict[str, str], list[dict[str, str]]]:
    documents = {}
    queries = []
    introduction = "This synthetic real estate handbook is for software evaluation only. It is not a company listing, policy, quotation or legal statement. Readers should confirm current details with the responsible office before making any commitment. "
    ending = " The customer service team can explain the process and record unresolved questions. Do not assume an unverified statement has been approved. These examples exist only to compare document segmentation under controlled local conditions."
    for source, facts, questions in FACTS:
        documents[source] = introduction + facts + ending
        queries.extend({"id": f"{source}-{index}", "query": query, "gold_source": source, "gold_evidence": facts.split(". ")[index - 1].rstrip(".")} for index, query in enumerate(questions, 1))
    return documents, queries


def tokens(text: str) -> list[str]:
    stop = {"the", "is", "a", "an", "of", "to", "and", "in", "for", "at", "what", "where", "when", "who", "does", "do", "are", "be", "can"}
    return [word for word in re.findall(r"\w+", text.casefold()) if word not in stop]


def benchmark_chunk_retrieval(documents: dict[str, str], queries: list[dict[str, str]]) -> dict[str, object]:
    configurations = []
    for size in (128, 256, 512):
        for overlap in (0, size // 4):
            chunks = [chunk for source, document in documents.items() for chunk in chunk_text(document, source, size, overlap)]
            term_counts = [Counter(tokens(chunk.text)) for chunk in chunks]
            document_frequency = Counter(term for counts in term_counts for term in counts)
            results = []
            for case in queries:
                query_terms = set(tokens(case["query"]))
                scores = [sum((1 + math.log(counts[term])) * math.log(1 + len(chunks) / (1 + document_frequency[term])) for term in query_terms if counts[term]) / math.sqrt(max(sum(counts.values()), 1)) for counts in term_counts]
                order = sorted(range(len(chunks)), key=lambda index: (-scores[index], index))[:3]
                sources = [str(chunks[index].metadata["source"]) for index in order if scores[index] > 0]
                gold = case["gold_source"]
                evidence = case.get("gold_evidence", "")
                support_hit = bool(evidence) and any(evidence.casefold() in chunks[index].text.casefold() for index in order if scores[index] > 0)
                results.append({**case, "retrieved_sources": sources, "hit_at_1": bool(sources) and sources[0] == gold, "hit_at_3": gold in sources, "complete_evidence_at_3": support_hit})
            total = len(results)
            configurations.append({"chunk_size_characters": size, "overlap_characters": overlap, "chunk_count": len(chunks), "source_accuracy_at_1": sum(item["hit_at_1"] for item in results) / total if total else 0.0, "source_recall_at_3": sum(item["hit_at_3"] for item in results) / total if total else 0.0, "complete_evidence_recall_at_3": sum(item["complete_evidence_at_3"] for item in results) / total if total else 0.0, "results": results})
    return {"mode": "synthetic-corpus-lexical-retrieval", "embedding_evidence": False, "company_data_evidence": False, "query_count": len(queries), "document_count": len(documents), "configurations": configurations}


def benchmark_vector_chunks(documents: dict[str, str], queries: list[dict[str, str]], embedding_provider: object, embedding_model: str) -> dict[str, object]:
    """Real embeddings and transient FAISS indexes; never touches the app index."""
    import faiss
    import numpy as np

    query_vectors = np.asarray(embedding_provider.embed([case["query"] for case in queries]), dtype="float32")
    faiss.normalize_L2(query_vectors)
    configurations = []
    for size in (128, 256, 512):
        for overlap in (0, size // 4):
            chunks = [chunk for source, document in documents.items() for chunk in chunk_text(document, source, size, overlap)]
            vectors = np.asarray(embedding_provider.embed([chunk.text for chunk in chunks]), dtype="float32")
            faiss.normalize_L2(vectors)
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            _, indices = index.search(query_vectors, 3)
            results = []
            for case, order in zip(queries, indices, strict=True):
                sources = [str(chunks[int(i)].metadata["source"]) for i in order if i >= 0]
                evidence = case.get("gold_evidence", "")
                results.append({**case, "retrieved_sources": sources,
                    "hit_at_1": bool(sources) and sources[0] == case["gold_source"],
                    "hit_at_3": case["gold_source"] in sources,
                    "complete_evidence_at_3": bool(evidence) and any(evidence.casefold() in chunks[int(i)].text.casefold() for i in order if i >= 0)})
            configurations.append({"chunk_size_characters": size, "overlap_characters": overlap,
                "chunk_count": len(chunks),
                "source_accuracy_at_1": sum(item["hit_at_1"] for item in results) / len(results),
                "source_recall_at_3": sum(item["hit_at_3"] for item in results) / len(results),
                "complete_evidence_recall_at_3": sum(item["complete_evidence_at_3"] for item in results) / len(results),
                "results": results})
    return {"mode": "synthetic-corpus-live-openai-embeddings-faiss", "embedding_evidence": True,
        "embedding_model": embedding_model, "company_data_evidence": False,
        "index_scope": "transient process-local FAISS; application knowledge store untouched",
        "query_count": len(queries), "document_count": len(documents), "configurations": configurations}
