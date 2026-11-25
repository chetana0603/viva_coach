"""
Grounding fixes, evaluated per concept on the DBMS notes.

1. Boilerplate removal: drop lines that repeat across the document (slide headers,
   footers, course codes) - a line seen >= MIN_REPEAT times is treated as template.
   Also drops course-administration pages (outline / objectives / outcomes / textbooks).
2. Coverage gate: a concept is 'covered' only if its best BM25 match clears a
   threshold relative to the corpus; otherwise generation is flagged for teacher
   attention instead of silently falling back on the LLM's own knowledge.

Prints, for each platform concept: how many syllabus/admin chunks reach the top-4
context before and after cleaning, the top chunk, and the coverage score.
"""
import collections
import re
import sys

import retrieval_eval as E

MIN_REPEAT = 25
ADMIN = re.compile(r"Course (Outline|Objectives|Outcomes|Evaluation)|Text ?books?|Reference Book|"
                   r"UE\d\dCS\d{3}|Acknowledgment|Hours\b", re.I)


def clean(raw):
    lines = raw.replace("\r\n", "\n").split("\n")
    freq = collections.Counter(l.strip() for l in lines if l.strip())
    kept = [l for l in lines if not (l.strip() and freq[l.strip()] >= MIN_REPEAT)
            and not re.fullmatch(r"\s*\d{1,4}\s*", l)]
    return "\n".join(kept), [s for s, c in freq.most_common(8) if c >= MIN_REPEAT]


def is_admin(chunk):
    return bool(ADMIN.search(chunk))


CONCEPTS = ["Relational Model and Keys", "Normalization and Functional Dependencies",
            "SQL Queries and Joins", "Transactions and ACID Properties",
            "Indexing and Query Performance", "ER Model and Schema Design"]

if __name__ == "__main__":
    notes = sys.argv[1]
    tp, rt = E.load_platform_core()
    raw = open(notes, encoding="utf-8", errors="ignore").read()

    before = tp.chunk_text(tp.normalize_text(raw))
    cleaned, removed = clean(raw)
    after = [c for c in tp.chunk_text(tp.normalize_text(cleaned)) if not is_admin(c)]
    print("boilerplate lines removed:", removed)
    print(f"chunks: {len(before)} -> {len(after)}")

    from rank_bm25 import BM25Okapi
    bm = BM25Okapi([tp.tokenize(c) for c in after])
    import numpy as np
    for c in CONCEPTS:
        b4 = rt.retrieve(c, chunks=before, top_k=4)
        q = rt.expand_query(c)
        s = bm.get_scores(q)
        order = np.argsort(-s)[:4]
        top = [after[i] for i in order]
        # coverage: best score as a z-score against the score distribution
        z = (s.max() - s.mean()) / (s.std() + 1e-9)
        print(f"\n{c}\n  admin chunks in top-4: before={sum(map(is_admin, b4))} "
              f"after={sum(map(is_admin, top))} | coverage z={z:.1f}")
        print("  #1 after:", top[0][:200].replace("\n", " "))
