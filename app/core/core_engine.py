"""
core_engine.py
--------------
All AI/LLM functions with robust offline fallbacks.

Primary LLM path: Groq (OpenAI-compatible chat completions). If no API key is
configured or a call fails, every function degrades gracefully to a deterministic
fallback so the whole app still runs and demos end-to-end.

Set the key via the sidebar in the app, or the GROQ_API_KEY environment variable.
"""

import os
import re

from app.core import prompts
from app.core.retriever import retrieve_context
from app.core.subject_bank import get_offline_mcqs
from app.core.text_processing import normalize_text, split_sentences, tokenize
from app.core.utils import extract_json, normalize_mcq, clamp_level, level_name, is_duplicate_question

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Overridable, because free-tier token budgets differ enormously between models
# and they get decommissioned periodically. Set GROQ_MODEL in .env to switch
# without touching code.
#
# On Groq's free tier the 70b model has a far smaller tokens-per-day allowance
# than the small instant models, and bulk question generation is exactly the
# workload that exhausts it. The 8b model is the sensible default for generating
# hundreds of candidates; a teacher reviews everything either way.
DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------
def get_api_key(explicit_key: str = None) -> str:
    return (explicit_key or os.environ.get("GROQ_API_KEY") or "").strip()


def llm_available(explicit_key: str = None) -> bool:
    return bool(get_api_key(explicit_key))


# Last failure reason from call_llm. Scripts read this to tell a rate limit or a
# dead model apart from a merely unhelpful answer — without it, every failure
# looks the same and you end up guessing.
LAST_ERROR = None
# Seconds to wait before retrying, when the API told us.
LAST_RETRY_AFTER = 0.0


def call_llm(prompt: str, api_key: str = None, model: str = DEFAULT_MODEL,
             temperature: float = 0.4, max_tokens: int = 900):
    """
    Call Groq's chat completions endpoint. Returns text, or None on failure with
    the reason recorded in LAST_ERROR.
    """
    global LAST_ERROR, LAST_RETRY_AFTER
    LAST_ERROR = None
    LAST_RETRY_AFTER = 0.0

    key = get_api_key(api_key)
    if not key:
        LAST_ERROR = "no_api_key"
        return None
    try:
        import requests
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise viva-preparation assistant. When asked for JSON, return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=45,
        )
        if resp.status_code == 429:
            body = resp.text[:400]
            # TPM clears within a minute; TPD does not clear until tomorrow.
            # Treating them the same wastes either a day or your patience.
            period = "day" if "per day" in body or "(TPD)" in body else "minute"
            retry_after = resp.headers.get("retry-after")
            try:
                wait = float(retry_after) if retry_after else (60.0 if period == "minute" else 0.0)
            except ValueError:
                wait = 60.0 if period == "minute" else 0.0
            LAST_ERROR = f"rate_limited_{period}"
            LAST_RETRY_AFTER = wait
            globals()["LAST_RETRY_AFTER"] = wait
            return None
        if resp.status_code in (401, 403):
            LAST_ERROR = f"auth_failed ({resp.status_code}): check GROQ_API_KEY"
            return None
        if resp.status_code == 404:
            LAST_ERROR = f"model_not_found: '{model}' may be decommissioned"
            return None
        if resp.status_code != 200:
            LAST_ERROR = f"http_{resp.status_code}: {resp.text[:200]}"
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        LAST_ERROR = f"{type(exc).__name__}: {exc}"
        return None


def check_llm(api_key: str = None, model: str = DEFAULT_MODEL):
    """One tiny call, to prove the API works before a long generation run."""
    reply = call_llm("Reply with exactly: OK", api_key=api_key, model=model,
                     max_tokens=10, temperature=0)
    return (True, "reachable") if reply else (False, LAST_ERROR or "unknown error")


# ---------------------------------------------------------------------------
# File text extraction (Project Viva)
# ---------------------------------------------------------------------------
CODE_EXTS = {".py", ".java", ".sql", ".c", ".cpp", ".h", ".html", ".css", ".js", ".txt", ".md"}


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    """Extract text from an uploaded file based on extension."""
    ext = os.path.splitext(filename)[1].lower()

    try:
        if ext == ".pdf":
            return _extract_pdf(file_bytes)
        if ext == ".docx":
            return _extract_docx(file_bytes)
        if ext in CODE_EXTS or True:  # everything else: treat as text
            return file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        try:
            return file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return ""


def _extract_pdf(file_bytes: bytes) -> str:
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx(file_bytes: bytes) -> str:
    import io
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


# ---------------------------------------------------------------------------
# Technology detection
# ---------------------------------------------------------------------------
TECH_SIGNATURES = {
    "Python": [r"\bimport\b", r"\bdef\b", r"\.py\b", r"streamlit", r"flask"],
    "Streamlit": [r"streamlit", r"st\.\w+"],
    "Flask": [r"flask", r"@app\.route"],
    "Java": [r"\bpublic\s+class\b", r"System\.out\.println", r"\.java\b"],
    "SQL": [r"\bSELECT\b", r"\bINSERT\b", r"\bCREATE TABLE\b", r"\bJOIN\b"],
    "SQLite": [r"sqlite3", r"\.db\b", r"sqlite"],
    "HTML/CSS/JavaScript": [r"<html", r"<div", r"function\s*\(", r"document\.", r"<script"],
    "C/C++": [r"#include", r"printf\s*\(", r"std::", r"\.cpp\b", r"\.c\b"],
    "Groq API": [r"groq", r"api\.groq\.com"],
    "REST API": [r"requests\.(get|post)", r"fetch\(", r"axios"],
}


def detect_technologies(text: str, api_key: str = None):
    """Detect technologies via LLM if available, else regex signatures."""
    text = normalize_text(text)
    if llm_available(api_key):
        context = text[:4000]
        raw = call_llm(prompts.TECH_DETECTION.format(context=context), api_key=api_key, max_tokens=300)
        parsed = extract_json(raw)
        if isinstance(parsed, dict) and parsed.get("technologies"):
            techs = [str(t).strip() for t in parsed["technologies"] if str(t).strip()]
            if techs:
                return sorted(set(techs))

    found = []
    for tech, patterns in TECH_SIGNATURES.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                found.append(tech)
                break
    return sorted(set(found))


# ---------------------------------------------------------------------------
# Concept extraction (Project Viva)
# ---------------------------------------------------------------------------
PROJECT_CONCEPT_KEYWORDS = {
    "Login / Authentication Module": ["login", "auth", "password", "signin", "credential"],
    "Database Layer": ["database", "sql", "sqlite", "table", "insert", "select", "query"],
    "Validation Logic": ["validate", "validation", "sanitize", "check input"],
    "Report Generation": ["report", "generate", "pdf", "export", "analytics"],
    "User Interface": ["ui", "streamlit", "html", "css", "button", "form", "page"],
    "Session / State Management": ["session", "state", "cookie", "token"],
    "API Integration": ["api", "requests", "endpoint", "groq", "fetch"],
    "File Handling": ["upload", "file", "read", "write", "parse"],
    "Search / Retrieval": ["search", "retrieve", "index", "chunk", "similarity"],
    "Scoring / Evaluation": ["score", "evaluate", "grade", "result", "accuracy"],
}


def extract_concepts(text: str, api_key: str = None):
    """
    Return {"concepts": [...], "technologies": [...]} for project material.
    LLM path if available, else keyword-based extraction.
    """
    text = normalize_text(text)
    technologies = detect_technologies(text, api_key=api_key)

    if llm_available(api_key):
        context = text[:5000]
        raw = call_llm(prompts.CONCEPT_EXTRACTION.format(context=context), api_key=api_key, max_tokens=500)
        parsed = extract_json(raw)
        if isinstance(parsed, dict) and parsed.get("concepts"):
            concepts = [str(c).strip() for c in parsed["concepts"] if str(c).strip()]
            techs = parsed.get("technologies") or technologies
            techs = [str(t).strip() for t in techs if str(t).strip()]
            if concepts:
                return {"concepts": concepts[:12], "technologies": sorted(set(techs))}

    # Fallback: keyword-based concept detection
    lower = text.lower()
    concepts = [name for name, kws in PROJECT_CONCEPT_KEYWORDS.items()
                if any(kw in lower for kw in kws)]

    # Add detected function/class names from code for richer coverage
    for match in re.findall(r"(?:def|class|function)\s+([A-Za-z_]\w+)", text)[:6]:
        pretty = match.replace("_", " ").title() + " Function/Class"
        if pretty not in concepts:
            concepts.append(pretty)

    if not concepts:
        concepts = ["Project Overview", "Main Functionality", "Data Handling"]
    return {"concepts": concepts[:12], "technologies": technologies}


# ---------------------------------------------------------------------------
# Learn Mode: study cards
# ---------------------------------------------------------------------------
def generate_study_card(concept: str, material: str, api_key: str = None):
    """Retrieval-grounded study card. LLM path if available, else context-derived."""
    context = retrieve_context(concept, text=material, top_k=4)

    if llm_available(api_key):
        raw = call_llm(
            prompts.LEARN_CARD.format(concept=concept, context=context or "(no context)"),
            api_key=api_key, max_tokens=700,
        )
        parsed = extract_json(raw)
        if isinstance(parsed, dict) and parsed.get("definition"):
            parsed["retrieved_context"] = context
            parsed["source"] = "AI (grounded)"
            return _ensure_card_fields(parsed, concept, context)

    return _fallback_card(concept, context)


def _ensure_card_fields(card, concept, context):
    card.setdefault("definition", f"{concept} is a key concept in this material.")
    card.setdefault("purpose", "It is used to solve a specific problem in the domain.")
    card.setdefault("where_used", "It appears in the relevant part of the syllabus/project.")
    card.setdefault("recommended_answer", card.get("definition", ""))
    card.setdefault("misconception", "Students often memorize the definition without understanding the purpose.")
    if not isinstance(card.get("revision_points"), list) or not card["revision_points"]:
        card["revision_points"] = ["Know the definition", "Know the purpose", "Know one what-if case"]
    card["retrieved_context"] = context
    return card


def _is_header_like(sentence: str) -> bool:
    """True for ALL-CAPS titles, numbered headings, or very short fragments."""
    s = sentence.strip()
    if len(s.split()) < 5:
        return True
    letters = [c for c in s if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
        return True  # mostly uppercase => heading
    if re.match(r"^\d+[.)]\s", s):
        return True
    return False


def _clean_sentences(context):
    """Sentences from context with headers and mid-sentence fragments removed."""
    out = []
    for s in split_sentences(context):
        if _is_header_like(s):
            continue
        # Drop fragments that begin mid-sentence (lowercase start) unless they
        # start with a common connective we can accept.
        if s[:1].islower():
            continue
        out.append(s)
    return out


def _fallback_card(concept, context):
    """Build a study card from retrieved context without an LLM."""
    sentences = _clean_sentences(context)
    concept_kw = [w for w in tokenize(concept) if len(w) > 3]

    # Prefer a definition sentence that mentions a concept keyword.
    definition = ""
    for s in sentences:
        if any(kw in s.lower() for kw in concept_kw):
            definition = s
            break
    if not definition:
        definition = sentences[0] if sentences else f"{concept} is a core concept in this material."

    purpose = ""
    where = ""
    for s in sentences:
        if s == definition:
            continue
        low = s.lower()
        if not purpose and any(w in low for w in ["used", "purpose", "helps", "prevent", "allows", "enables", "reduce"]):
            purpose = s
        elif not where and any(w in low for w in ["applied", "during", "where", "when converting", "in design"]):
            where = s
    purpose = purpose or f"{concept} is used to address a specific need in this domain."
    where = where or "It is applied in the relevant stage of the design/implementation."

    recommended = definition
    if purpose:
        recommended = f"{definition} {purpose}"

    return {
        "definition": definition,
        "purpose": purpose,
        "where_used": where,
        "recommended_answer": recommended[:400],
        "misconception": "Memorizing the definition without being able to explain its purpose or a failure case.",
        "revision_points": [
            f"What {concept} is (definition)",
            f"Why {concept} is used (purpose)",
            f"What happens if {concept} is ignored (what-if)",
        ],
        "retrieved_context": context,
        "source": "Offline (context-grounded)",
    }


# ---------------------------------------------------------------------------
# Practice Mode: MCQ generation
# ---------------------------------------------------------------------------
def generate_mcq(concept: str, level: int, material: str, previous_questions=None,
                 api_key: str = None):
    """
    Generate one MCQ at the target level.
    LLM path if available; otherwise use the offline bank or template fallback.
    """
    level = clamp_level(level)
    previous_questions = previous_questions or []

    # Widen retrieval as more questions exist for this concept. Feeding the model
    # the same three chunks every time is why repeated calls produced near-identical
    # questions: identical input, identical output.
    # Context is the bulk of each request, so cap it: more context does not make a
    # better single MCQ, it just burns the daily token budget faster.
    top_k = 3 + min(len(previous_questions) // 4, 3)
    context = retrieve_context(concept, text=material, top_k=top_k, max_chars=1200)

    if llm_available(api_key):
        # Show more history than before. The model can only avoid duplicates it
        # has been shown, and five was too few once a concept had a dozen.
        # Send question stems only, not whole questions — enough for the model to
        # avoid repeats, at a fraction of the tokens.
        recent = [q[:90] for q in previous_questions[-10:]]
        prev = "\n".join(f"- {q}" for q in recent) if recent else "(none yet)"

        # Raise temperature as the pool fills, so later calls explore further.
        temperature = min(0.6 + 0.05 * len(previous_questions), 1.0)

        raw = call_llm(
            prompts.MCQ_GENERATION.format(
                concept=concept, level=level, level_name=level_name(level),
                level_guide=prompts.LEVEL_GUIDE, previous=prev,
                context=context or "(no context)",
            ),
            api_key=api_key, max_tokens=550, temperature=temperature,
        )
        parsed = normalize_mcq(extract_json(raw))
        if parsed and not is_duplicate_question(parsed["question"], previous_questions):
            parsed["concept"] = concept
            parsed["source"] = "AI"
            return parsed

        # Record which of the two happened, so callers do not have to guess.
        global LAST_ERROR
        if raw is None:
            pass                      # LAST_ERROR already set by call_llm
        elif parsed is None:
            LAST_ERROR = "unparseable_response"
        else:
            LAST_ERROR = "duplicate_question"

    return _fallback_mcq(concept, level, context, previous_questions)


def generate_remedial_mcq(concept: str, failed_question: str, wrong_answer: str,
                          correct_answer: str, level: int, material: str,
                          previous_questions=None, api_key: str = None):
    """Generate a simpler hint-style remedial MCQ after a wrong answer."""
    level = clamp_level(level)
    previous_questions = previous_questions or []
    context = retrieve_context(concept, text=material, top_k=3)

    if llm_available(api_key):
        raw = call_llm(
            prompts.REMEDIAL_MCQ.format(
                concept=concept, failed_question=failed_question,
                wrong_answer=wrong_answer, correct_answer=correct_answer,
                level=level, level_name=level_name(level),
                context=context or "(no context)",
            ),
            api_key=api_key, max_tokens=500, temperature=0.6,
        )
        parsed = normalize_mcq(extract_json(raw))
        if parsed and not is_duplicate_question(parsed["question"], previous_questions):
            parsed["concept"] = concept
            parsed["remedial"] = True
            parsed["source"] = "AI"
            return parsed

    mcq = _fallback_mcq(concept, level, context, previous_questions)
    mcq["remedial"] = True
    return mcq


def _fallback_mcq(concept, level, context, previous_questions):
    """
    Offline MCQ: prefer the hand-authored subject bank; otherwise build a
    template question grounded in the retrieved context.
    """
    # 1) Try the offline bank for this concept at (or near) the target level
    bank = get_offline_mcqs(concept)
    if bank:
        # Prefer exact level, then any unused question
        candidates = [q for q in bank if q.get("level") == level]
        candidates += [q for q in bank if q.get("level") != level]
        for q in candidates:
            if not is_duplicate_question(q["question"], previous_questions):
                mcq = normalize_mcq({**q, "concept": concept})
                if mcq:
                    mcq["concept"] = concept
                    mcq["source"] = "Offline bank"
                    return mcq

    # 2) Template fallback grounded in context
    return _template_mcq(concept, level, context, previous_questions)


def _template_mcq(concept, level, context, previous_questions):
    sentences = split_sentences(context)
    grounded = sentences[0] if sentences else f"{concept} is a core concept."
    grounded = grounded[:160]

    templates = {
        0: (f"Which statement best describes {concept}?",
            [grounded,
             f"{concept} is an unrelated networking protocol.",
             f"{concept} is a type of physical hardware only.",
             f"{concept} has no defined meaning in this subject."], 0),
        1: (f"What is the main purpose of {concept}?",
            ["To solve a specific problem correctly and efficiently in this domain",
             "To intentionally slow down the system",
             "To increase redundancy and errors on purpose",
             "It serves no purpose"], 0),
        2: (f"How does {concept} relate to the other ideas in this topic?",
            ["It connects to and supports related concepts in the topic",
             "It is completely isolated from every other idea",
             "It replaces the entire subject",
             "It contradicts all other concepts"], 0),
        3: (f"Where is {concept} typically applied?",
            ["In the relevant stage of the design or implementation",
             "Only in unrelated hardware manuals",
             "Never applied anywhere in practice",
             "Only in cooking recipes"], 0),
        4: (f"What happens if {concept} is ignored or removed?",
            ["Problems, errors, or inefficiency can result",
             "The system always improves",
             "Absolutely nothing changes ever",
             "It becomes automatically encrypted"], 0),
        5: (f"Why might a designer make deliberate trade-offs around {concept}?",
            ["To balance competing goals like performance, cost, and correctness",
             "Because trade-offs are illegal",
             "To guarantee there is only one possible design",
             "Because it deletes all data"], 0),
    }
    q, opts, ans = templates.get(level, templates[0])
    return normalize_mcq({
        "question": q, "options": opts, "answer": ans,
        "explanation": f"The correct option reflects the actual role of {concept} in this material.",
        "level": level, "concept": concept,
    }) | {"source": "Template", "concept": concept}


# ---------------------------------------------------------------------------
# Descriptive question (integrity demo)
# ---------------------------------------------------------------------------
def generate_descriptive_question(concept: str, material: str, api_key: str = None):
    context = retrieve_context(concept, text=material, top_k=3)
    if llm_available(api_key):
        raw = call_llm(
            prompts.DESCRIPTIVE_QUESTION.format(concept=concept, context=context or "(no context)"),
            api_key=api_key, max_tokens=300,
        )
        parsed = extract_json(raw)
        if isinstance(parsed, dict) and parsed.get("question"):
            return {"question": parsed["question"], "model_answer": parsed.get("model_answer", "")}

    return {
        "question": f"In 3-4 lines, explain why {concept} is important and what would go wrong without it.",
        "model_answer": f"{concept} is important because it addresses a core need in this material; ignoring it leads to errors or inefficiency.",
    }


# ---------------------------------------------------------------------------
# Teacher report
# ---------------------------------------------------------------------------
def generate_teacher_report(analytics_summary: str, api_key: str = None):
    """LLM-enriched teacher report; falls back to a structured template message."""
    if llm_available(api_key):
        raw = call_llm(
            prompts.TEACHER_REPORT.format(summary=analytics_summary),
            api_key=api_key, max_tokens=500,
        )
        parsed = extract_json(raw)
        if isinstance(parsed, dict) and parsed.get("interpretation"):
            return {
                "interpretation": str(parsed.get("interpretation", "")).strip(),
                "weak_summary": str(parsed.get("weak_summary", "")).strip(),
                "followup_questions": [str(q).strip() for q in (parsed.get("followup_questions") or []) if str(q).strip()],
                "integrity_note": str(parsed.get("integrity_note", "")).strip(),
            }
    return None  # caller falls back to scoring.teacher_followups
