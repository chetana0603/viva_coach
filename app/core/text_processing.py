"""
text_processing.py
------------------
Normalizes raw text (from backend notes, uploaded files, code) and splits it
into overlapping chunks so the retriever can find concept-specific context.

This is deliberately dependency-free (pure Python) so the pipeline runs anywhere.
"""

import re


def normalize_text(text: str) -> str:
    """Clean junk, collapse whitespace, standardize newlines."""
    if not text:
        return ""

    # Standardize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove non-printable / control characters (keep normal whitespace)
    text = re.sub(r"[^\x09\x0a\x0d\x20-\x7e\u00a0-\uffff]", " ", text)

    # Collapse 3+ blank lines into a paragraph break
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse runs of spaces/tabs
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Trim trailing spaces on each line
    text = "\n".join(line.strip() for line in text.split("\n"))

    # Join hard-wrapped lines *within* a paragraph into single lines, so that
    # sentence splitting is not broken by mid-sentence newlines. Paragraph
    # breaks (blank lines) are preserved.
    def _looks_heading(s):
        letters = [c for c in s if c.isalpha()]
        return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.7

    paragraphs = re.split(r"\n{2,}", text)
    rejoined = []
    for para in paragraphs:
        lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
        merged = []
        for ln in lines:
            can_merge = (
                merged
                and len(ln.split()) >= 3
                and not re.match(r"^\d+[.)]\s", ln)
                and not _looks_heading(ln)
                and not _looks_heading(merged[-1])
            )
            if can_merge:
                merged[-1] = merged[-1] + " " + ln
            else:
                merged.append(ln)
        rejoined.append("\n".join(merged))
    text = "\n\n".join(rejoined)

    return text.strip()


def split_sentences(text: str):
    """Very light sentence splitter used for descriptive-answer analysis."""
    text = normalize_text(text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150):
    """
    Split text into overlapping character chunks.

    Overlap matters: a concept explanation may straddle two chunks, and overlap
    keeps the retriever from cutting an idea in half.
    """
    text = normalize_text(text)
    if not text:
        return []

    if chunk_size <= 0:
        return [text]

    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)

        # Try to break on a paragraph or sentence boundary near the end
        if end < n:
            window = text[start:end]
            break_at = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if break_at > chunk_size * 0.5:
                end = start + break_at + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= n:
            break
        start = max(end - overlap, start + 1)

    return chunks


def tokenize(text: str):
    """Lowercase word tokens, used by the retriever and integrity checks."""
    return re.findall(r"[a-z0-9]+", (text or "").lower())
