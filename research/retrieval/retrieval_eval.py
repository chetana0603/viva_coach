"""
E4 - Retrieval comparison for grounding question generation.

Methods
  tfidf   : the platform's own retriever (app/core/retriever.py, with query expansion)
  bm25    : Okapi BM25 over the same chunks (rank_bm25)
  dense   : sentence-transformers all-MiniLM-L6-v2 cosine (skipped if unavailable)
  hybrid  : reciprocal-rank fusion of bm25 + dense (or bm25 + tfidf without dense)

Two modes:
  python retrieval_eval.py pool  QUERIES.csv NOTES.txt   -> judgments_to_fill.csv
      Pools the top-k chunks from every method per query (TREC-style), shuffled and
      without method labels, so annotators judge relevance blind.
  python retrieval_eval.py score QUERIES.csv NOTES.txt judgments_filled.csv
      Computes P@k, Recall@k (over pooled relevant), MRR and nDCG@k per method.

QUERIES.csv needs columns: query_id, query   (e.g. the question text of each
approved question; the concept name can be prepended).
"""
import csv
import importlib.util
import math
import os
import random
import sys
import types

K = 5
HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = os.environ.get("VIVA_PLATFORM_DIR", os.path.join(HERE, "..", ".."))


def load_platform_core():
    """Import app.core.text_processing / retriever without importing Flask."""
    pkg_app, pkg_core = types.ModuleType("app"), types.ModuleType("app.core")
    pkg_app.__path__, pkg_core.__path__ = [], []
    sys.modules.setdefault("app", pkg_app)
    sys.modules.setdefault("app.core", pkg_core)
    mods = {}
    for name in ("text_processing", "retriever"):
        path = os.path.join(PLATFORM, "app", "core", f"{name}.py")
        spec = importlib.util.spec_from_file_location(f"app.core.{name}", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"app.core.{name}"] = mod
        spec.loader.exec_module(mod)
        mods[name] = mod
    return mods["text_processing"], mods["retriever"]


def read_queries(path):
    """Accepts either (query_id, query) or the questions_DBMS.csv export
    (question_id, concept, question_text); approved questions only."""
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if rows and "query" in rows[0]:
        return [(r["query_id"], r["query"]) for r in rows]
    return [(r["question_id"], f'{r["concept"]}: {r["question_text"]}') for r in rows
            if r.get("review_status", "approved") == "approved"]


class Retrievers:
    def __init__(self, chunks, tp, rt):
        self.chunks, self.tp, self.rt = chunks, tp, rt
        from rank_bm25 import BM25Okapi
        self.bm25 = BM25Okapi([tp.tokenize(c) for c in chunks])
        self.dense = None
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            self.dense = self.model.encode(chunks, normalize_embeddings=True,
                                           show_progress_bar=False)
        except Exception as e:  # noqa: BLE001 - offline environments
            print(f"[dense retrieval skipped: {type(e).__name__}]")
        self._tfidf_cache = None

    def tfidf(self, q, k):
        # Use the platform's own scoring so the baseline is exactly what ships.
        doc_tokens, idf = self.rt._build_index(self.chunks)
        qvec = self.rt._vectorize(self.rt.expand_query(q), idf)
        qtok = set(self.rt.expand_query(q))
        scored = []
        for i, toks in enumerate(doc_tokens):
            s = self.rt._cosine(qvec, self.rt._vectorize(toks, idf)) + 0.01 * len(qtok & set(toks))
            scored.append((s, i))
        scored.sort(reverse=True)
        return [i for _, i in scored[:k]]

    def bm25_rank(self, q, k):
        s = self.bm25.get_scores(self.tp.tokenize(q))
        return sorted(range(len(s)), key=lambda i: -s[i])[:k]

    def dense_rank(self, q, k):
        if self.dense is None:
            return []
        qv = self.model.encode([q], normalize_embeddings=True, show_progress_bar=False)[0]
        s = self.dense @ qv
        return sorted(range(len(s)), key=lambda i: -s[i])[:k]

    def hybrid(self, q, k, depth=50):
        a = self.bm25_rank(q, depth)
        b = self.dense_rank(q, depth) or self.tfidf(q, depth)
        score = {}
        for ranking in (a, b):
            for r, i in enumerate(ranking):
                score[i] = score.get(i, 0) + 1 / (60 + r + 1)
        return sorted(score, key=lambda i: -score[i])[:k]

    def methods(self):
        m = {"tfidf": self.tfidf, "bm25": self.bm25_rank, "hybrid": self.hybrid}
        if self.dense is not None:
            m["dense"] = self.dense_rank
        return m


def setup(notes_path):
    tp, rt = load_platform_core()
    text = tp.normalize_text(open(notes_path, encoding="utf-8", errors="ignore").read())
    chunks = tp.chunk_text(text)            # platform defaults: 900 chars, 150 overlap
    return Retrievers(chunks, tp, rt)


def pool(queries_csv, notes_path, out="judgments_to_fill.csv", seed=13):
    R = setup(notes_path)
    rng = random.Random(seed)
    rows = []
    for qid, q in read_queries(queries_csv):
        ids = set()
        for fn in R.methods().values():
            ids.update(fn(q, K))
        ids = list(ids)
        rng.shuffle(ids)
        rows += [(qid, q, i, R.chunks[i]) for i in ids]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query_id", "query", "chunk_id", "chunk_text",
                    "relevant (2=answers it, 1=partly, 0=no)"])
        for r in rows:
            w.writerow(list(r) + [""])
    print(f"{len(R.chunks)} chunks; methods={list(R.methods())}; wrote {len(rows)} pairs -> {out}")


def score(queries_csv, notes_path, judged_csv):
    R = setup(notes_path)
    rel = {}
    with open(judged_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v = (r.get("relevant (2=answers it, 1=partly, 0=no)") or r.get("relevant") or "").strip()
            if v != "":
                rel[(r["query_id"], int(r["chunk_id"]))] = int(v)
    queries = read_queries(queries_csv)
    results = {}
    for name, fn in R.methods().items():
        p, rc, mrr, ndcg, n = 0, 0, 0, 0, 0
        for qid, q in queries:
            judged_rel = [c for (qq, c), v in rel.items() if qq == qid and v >= 1]
            if not judged_rel:
                continue
            ranked = fn(q, K)
            gains = [rel.get((qid, c), 0) for c in ranked]
            hits = [g >= 1 for g in gains]
            p += sum(hits) / K
            rc += sum(hits) / len(judged_rel)
            mrr += next((1 / (i + 1) for i, h in enumerate(hits) if h), 0)
            dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))
            ideal = sorted([v for (qq, c), v in rel.items() if qq == qid], reverse=True)[:K]
            idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
            ndcg += dcg / idcg if idcg else 0
            n += 1
        results[name] = {f"P@{K}": p / n, f"R@{K}": rc / n, "MRR": mrr / n,
                         f"nDCG@{K}": ndcg / n, "n_queries": n}
    for name, r in results.items():
        print(name, {k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()})
    return results


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "pool":
        pool(sys.argv[2], sys.argv[3])
    elif mode == "score":
        score(sys.argv[2], sys.argv[3], sys.argv[4])
