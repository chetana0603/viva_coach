# prompts.py

LEARN_MODE_PROMPT = """
You are an expert university examiner. Generate a concise, highly technical study card for the concept based ONLY on the provided textbook context chunks.

Concept: {concept_name}
Context: {context_text}

Provide your response in the following JSON format exactly:
{{
    "definition": "Clear, technical 2-sentence definition.",
    "purpose": "Why this concept is essential in the real world.",
    "where_used": "Practical application area or architectural layer.",
    "recommended_viva_answer": "A perfect, high-scoring 3-line response a student should give to an examiner.",
    "common_misconception": "One trap students fall into during viva regarding this topic.",
    "quick_revision_points": [
        "Key point 1",
        "Key point 2"
    ]
}}
"""

PRACTICE_MODE_PROMPT = """
You are a university viva board director running an adaptive exam. Generate exactly ONE Multiple Choice Question (MCQ) matching the requested difficulty Level.

Target Level: {level}
Level Guidelines:
- Level 0 (Recognition): Basic definitions, matching terms.
- Level 1 (Purpose): Why it is used, primary goals.
- Level 2 (Relationship): Differences, contrasts, connections.
- Level 3 (Application): Code scenarios, architectural use cases.
- Level 4 (What-if): Failures, errors, consequences of removing the component.
- Level 5 (Design Reasoning): Trade-offs, optimization justifications.

Concept: {concept_name}
Context: {context_text}
Remedial Mode Active: {remedial_mode}
Previous Attempt Context: {remedial_context}

CRITICAL RULES:
1. Question must be under 20 words.
2. If Remedial Mode is True, do NOT repeat the previous question; instead, ask a simpler, highly foundational hint-style question to rebuild basic confidence.
3. Provide exactly 4 realistic, distinct options labeled A, B, C, D.

Provide your response in the following JSON format exactly:
{{
    "question": "The question text here?",
    "options": {{
        "A": "Option text A",
        "B": "Option text B",
        "C": "Option text C",
        "D": "Option text D"
    }},
    "correct_answer": "A, B, C, or D",
    "explanation": "Clear, precise diagnostic explanation detailing why the answer is correct and why others are false."
}}
"""

DESCRIPTIVE_QUESTION_PROMPT = """
You are a viva examiner evaluating final conceptual clarity and communication skill.
Generate exactly ONE concise, analytical descriptive question about the following concept based on the retrieved context.

Concept: {concept_name}
Context: {context_text}

The question should challenge the student to explain a "why" or "how" mechanism in 3 to 4 lines.

Provide your response in the following JSON format exactly:
{{
    "question": "Descriptive question text here."
}}
"""

TEACHER_REPORT_PROMPT = """
You are a senior academic analyst. Based on the student's complete exam trace records, write a succinct review analysis for the evaluating professor.

Student Performance Trace: {history_trace}
Weak Concepts Identified: {weak_concepts}
Strong Concepts Identified: {strong_concepts}

Provide your response in the following JSON format exactly:
{{
    "report_summary": "A cohesive 3-sentence summary summarizing student depth of understanding, pacing anomalies, and foundational gaps.",
    "readiness_interpretation": "A diagnostic review regarding whether the student is authentically prepared or prone to failure.",
    "suggested_follow_up_questions": [
        "1. Precise specific targeted follow-up question regarding a weak concept.",
        "2. Another deep architectural or failure-mode follow-up question.",
        "3. A trade-off question to verify authentic conceptual grasp."
    ]
}}
"""
CONCEPT_EXTRACTION_PROMPT = """
You are an expert academic curator. Analyze the following text corpus extracted from academic notes or project files.
Extract a list of the top 5 distinct, core technical concepts or modules that are crucial for a viva voice examination.

Subject context: {subject}
Text Corpus (Sample): {corpus_sample}

Provide your response in the following JSON format exactly, containing a simple array of strings:
{{
    "concepts": [
        "Concept Name 1",
        "Concept Name 2",
        "Concept Name 3",
        "Concept Name 4",
        "Concept Name 5"
    ]
}}
"""