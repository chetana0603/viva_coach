"""
retriever.py
------------
Finds the most relevant chunks for a selected concept.

Uses a lightweight, dependency-free TF-IDF + cosine similarity implementation so
Learn Mode and Practice Mode are grounded in the right part of the material
instead of just the first page. Query is expanded with related terms so that,
e.g. "Virtual Memory and Paging" also matches "page fault", "frame", "TLB".
"""

import math
from collections import Counter

from app.core.text_processing import chunk_text, tokenize

# Query expansion map: concept keyword -> related terms that should also match.
EXPANSION = {
    "normalization": ["functional", "dependency", "anomaly", "redundancy", "decompose", "1nf", "2nf", "3nf", "bcnf"],
    "key": ["primary", "foreign", "candidate", "super", "unique", "attribute"],
    "relational": ["table", "tuple", "relation", "attribute", "schema", "domain"],
    "transaction": ["acid", "commit", "rollback", "atomicity", "isolation", "concurrency"],
    "index": ["btree", "hashing", "search", "lookup", "performance"],
    "join": ["inner", "outer", "natural", "equi", "cartesian"],
    "paging": ["page", "fault", "frame", "tlb", "virtual", "memory", "swap"],
    "scheduling": ["cpu", "burst", "round", "robin", "fcfs", "sjf", "priority", "quantum"],
    "deadlock": ["mutual", "exclusion", "hold", "wait", "preemption", "banker"],
    "synchronization": ["semaphore", "mutex", "critical", "section", "race", "lock"],
    "process": ["thread", "pcb", "state", "context", "switch", "fork"],
    "file": ["directory", "inode", "allocation", "block", "storage"],
    "authentication": ["login", "password", "session", "token", "credential", "verify"],
    "validation": ["input", "sanitize", "check", "form", "constraint"],
    "database": ["sql", "query", "table", "sqlite", "insert", "select"],
}


def expand_query(concept: str):
    tokens = tokenize(concept)
    expanded = list(tokens)
    for tok in tokens:
        for key, extra in EXPANSION.items():
            if key.startswith(tok) or tok.startswith(key):
                expanded.extend(extra)
    return expanded


def _build_index(chunks):
    """Compute document frequencies for IDF."""
    doc_tokens = [tokenize(c) for c in chunks]
    df = Counter()
    for toks in doc_tokens:
        for t in set(toks):
            df[t] += 1
    n_docs = len(chunks)
    idf = {t: math.log((n_docs + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    return doc_tokens, idf


def _vectorize(tokens, idf):
    tf = Counter(tokens)
    vec = {t: (freq / len(tokens)) * idf.get(t, 1.0) for t, freq in tf.items()} if tokens else {}
    return vec


def _cosine(a, b):
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def retrieve(concept: str, text: str = None, chunks=None, top_k: int = 4):
    """
    Return the top_k most relevant chunks for a concept.

    Accepts either raw `text` (which it will chunk) or pre-computed `chunks`.
    """
    if chunks is None:
        chunks = chunk_text(text or "")
    if not chunks:
        return []

    doc_tokens, idf = _build_index(chunks)
    query_tokens = expand_query(concept)
    qvec = _vectorize(query_tokens, idf)

    scored = []
    for i, toks in enumerate(doc_tokens):
        dvec = _vectorize(toks, idf)
        score = _cosine(qvec, dvec)
        # Small keyword-overlap bonus so exact concept mentions rank higher
        overlap = len(set(query_tokens) & set(toks))
        scored.append((score + overlap * 0.01, i))

    scored.sort(reverse=True)
    selected = [chunks[i] for score, i in scored[:top_k] if score > 0]

    # If nothing scored (very short/odd material), fall back to first chunks
    if not selected:
        selected = chunks[:top_k]
    return selected


def retrieve_context(concept: str, text: str = None, chunks=None, top_k: int = 4, max_chars: int = 2000):
    """Convenience: retrieve chunks and join them into a single context string."""
    top = retrieve(concept, text=text, chunks=chunks, top_k=top_k)
    context = "\n\n---\n\n".join(top)
    return context[:max_chars]
