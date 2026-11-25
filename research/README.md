# Research experiments for the ICIET 2027 paper

Deadline: **10 December 2026** (EasyChair, IEEE proceedings, ~5 pages).

## E2 — Simulation of the adaptive engine (`simulation/`) — done

`simulate.py` replicates the platform's rules exactly (±1 staircase, remedial at L−1 after a
wrong primary answer in the post-test, readiness formula from `app/core/scoring.py`) with
simulated Rasch learners, calibrated so the simulated pre-test matches the pilot
(primary ≈ 49 %). `cat_compare.py` compares staircase routing with EAP-driven routing.

Key results (`sim_results.json`, `cat_results.json`):

| With ZERO real learning, post − pre | mean gain | "significant" at n = 16 |
|---|---|---|
| Highest level reached (attempted) | **+0.30 levels** | **16 %** of studies |
| Highest level answered correctly | +0.36 levels | 17 % |
| Readiness (code) | −0.04 | 2.5 % |
| Primary score % | −2.0 pts | 0.5 % |
| EAP ability (all responses) | −0.001 | 2.5 % |

- Remediation alone inflates "highest level", so that pilot result is unreliable.
  Primary score and readiness are biased slightly *down*, so those gains are conservative.
- EAP ability is unbiased, tracks true ability best (r = 0.90) and has the most power
  (0.87 vs 0.42 for primary % at Δθ = 0.5, n = 16).
- Routing by EAP barely beats the staircase (RMSE 0.435 vs 0.440). Scoring with all
  responses, remedials included, matters more (RMSE 0.44 → 0.37).
  → Keep the staircase; change the score.
- The bias holds across difficulty spacings 0.5–1.0 logits/level and mean ability −0.5…+0.5.

Run: `python simulate.py` (~4 min), `python cat_compare.py` (~10 s).

## E4 — Retrieval and grounding (`retrieval/`) — harness ready, needs data

`retrieval_eval.py pool QUERIES.csv NOTES.txt` writes a blind judging sheet (top-5 from each
method, pooled and shuffled); `score` computes P@5, R@5, MRR, nDCG@5.
Methods: the platform's TF-IDF, BM25, MiniLM dense embeddings, hybrid (RRF).
Dense retrieval needs `pip install sentence-transformers rank_bm25` and internet access on
first run, so run it on your machine.

Findings so far (`grounding_fix.py`):
1. The repeated slide header and the syllabus page pollute retrieval. For
   *Normalization*, 3 of the 4 context chunks the generator received were course-outline text.
   Removing lines that repeat ≥ 25 times plus the admin pages brings this to 0 for every concept.
2. The notes barely cover two concepts: "functional dependency" ×3, "normal form" ×2,
   BCNF ×0, B+ tree ×1. Questions on these cannot be grounded in the course material.
3. `retrieve_context` caps the context at 2,000 characters, so only ~2 of the 4 retrieved
   900-character chunks reach the LLM.
4. A lexical coverage score does not detect shallow coverage (Normalization scores highest).
   Coverage has to be judged per question: does `source_text` support the correct answer?

## Still needed from you
- `python scripts/export_study_data.py <study_group>` → send `study_export/*.csv`
  (gives E1 re-analysis, E3 rating sheet, E4 queries).
- Whether Prof. Kumar plus one more faculty member can rate ~100 questions (E3).
