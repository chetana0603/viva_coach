"""
prompts.py
----------
All LLM prompt templates. Kept separate so prompts can be tuned without touching
engine logic. Every generation prompt demands strict JSON so output can be parsed
reliably by utils.extract_json.
"""

LEVEL_GUIDE = """Difficulty levels (0 = easiest, 5 = hardest). Higher levels must
be genuinely harder questions on the same concept:
Level 0 - Very Easy: recall a single basic fact or definition
Level 1 - Easy: a straightforward question about one idea
Level 2 - Moderate: requires connecting or comparing two ideas
Level 3 - Challenging: apply the concept to a concrete situation
Level 4 - Hard: reason about consequences, edge cases, or errors
Level 5 - Expert: analyse trade-offs and justify a design decision"""


CONCEPT_EXTRACTION = """You are helping a student prepare for a project viva.
From the project material below, extract the key viva-relevant components a
teacher would ask about: modules, functions, database tables, algorithms,
validation logic, authentication logic, reports, and UI components.

Return ONLY valid JSON in this exact shape, no prose:
{{
  "concepts": ["...", "..."],
  "technologies": ["...", "..."]
}}

Give 6-12 concise concept names and any technologies you can identify.

PROJECT MATERIAL:
{context}
"""


LEARN_CARD = """You are a viva-preparation tutor. Using ONLY the retrieved context
below, produce a study card for the concept: "{concept}".

Return ONLY valid JSON in this exact shape, no prose:
{{
  "definition": "1-2 sentence definition grounded in the context",
  "purpose": "why it is used",
  "where_used": "where/how it is applied",
  "recommended_answer": "a strong 2-3 sentence viva answer",
  "misconception": "a common misconception students have",
  "revision_points": ["short point", "short point", "short point"]
}}

If the context does not cover something, stay faithful to the context and keep it
general rather than inventing specifics.

RETRIEVED CONTEXT:
{context}
"""

MCQ_GENERATION = """You are a viva examiner. Based ONLY on the retrieved context below, generate ONE multiple-choice question for the concept "{concept}" at difficulty Level {level} ({level_name}).

{level_guide}

QUESTIONS ALREADY WRITTEN FOR THIS CONCEPT — your question must be clearly different
from all of them. Ask about a different aspect, use a different scenario, and do not
merely reword these:
{previous}

Pick an angle none of the above covers. If the obvious question has been asked, go for a
narrower detail, a comparison, a concrete example, or a consequence.

Return ONLY valid JSON, no prose:
{{
  "question": "...",
  "options": ["A", "B", "C", "D"],
  "answer": 0,
  "explanation": "General core concept explanation...",
  "options_breakdown": {{
    "0": "Explanation for option 0 (Why it is correct)...",
    "1": "Explanation for option 1 (Why it is incorrect)...",
    "2": "Explanation for option 2 (Why it is incorrect)...",
    "3": "Explanation for option 3 (Why it is incorrect)..."
  }},
  "level": {level}
}}

RETRIEVED CONTEXT:
{context}
"""

REMEDIAL_MCQ = """You are a supportive tutor. The student answered a Level {level} question incorrectly on the concept "{concept}".
To fix their foundation, generate a remedial question at difficulty Level {level} ({level_name}). 
Ground it entirely in the retrieved context below.

Concept: "{concept}"
Failed question: "{failed_question}"
Student's wrong answer: "{wrong_answer}"
Correct answer was: "{correct_answer}"

Return ONLY valid JSON, no prose:
{{
  "question": "...",
  "options": ["A", "B", "C", "D"],
  "answer": 0,
  "explanation": "General core concept explanation...",
  "options_breakdown": {{
    "0": "Explanation for option 0...",
    "1": "Explanation for option 1...",
    "2": "Explanation for option 2...",
    "3": "Explanation for option 3..."
  }},
  "level": {level}
}}

RETRIEVED CONTEXT:
{context}
"""


DESCRIPTIVE_QUESTION = """Generate ONE short descriptive viva question for the
concept "{concept}" that asks the student to explain in 3-4 lines. It should test
real understanding (purpose, reasoning, or a what-if), not just a definition.

Return ONLY valid JSON, no prose:
{{
  "question": "In 3-4 lines, ...",
  "model_answer": "a concise ideal answer"
}}

RETRIEVED CONTEXT:
{context}
"""


TEACHER_REPORT = """You are assisting a teacher evaluating a student's viva
readiness. Based on the analytics summary below, write a short teacher-facing
review. Be concise and practical.

Return ONLY valid JSON, no prose:
{{
  "interpretation": "2-3 sentence readiness interpretation",
  "weak_summary": "1-2 sentences on weak areas",
  "followup_questions": ["...", "...", "..."],
  "integrity_note": "1 sentence caution about any integrity signals, or 'No integrity concerns.'"
}}

ANALYTICS SUMMARY:
{summary}
"""


TECH_DETECTION = """Identify the technologies, languages, frameworks, and
databases used in this project material. Return ONLY valid JSON:
{{"technologies": ["...", "..."]}}

MATERIAL:
{context}
"""
