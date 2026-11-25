# core_engine.py
import os
import json
import prompts
from groq import Groq
from utils import parse_llm_json

def get_groq_client():
    """Initializes the Groq client using the system environment API key."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable not set. Please configure it.")
    return Groq(api_key=api_key)

def call_groq_json(prompt: str) -> dict:
    """Helper function that executes a chat completion on Groq with forced JSON format output."""
    client = get_groq_client()
    
    # We use llama-3.3-70b-versatile for top-tier conceptual logic and JSON accuracy.
    # For ultra-low latency, you can swap to "llama3-8b-8192".
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "value": "You are a precise, technical academic evaluator who outputs valid JSON objects exclusively."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    
    raw_text = response.choices[0].message.content
    return parse_llm_json(raw_text)

def generate_study_card(concept_name: str, context_chunks: list) -> dict:
    context_text = "\n\n".join(context_chunks)
    prompt = prompts.LEARN_MODE_PROMPT.format(concept_name=concept_name, context_text=context_text)
    return call_groq_json(prompt)

def generate_adaptive_mcq(concept_name: str, context_chunks: list, level: int, remedial_mode: bool, history: list) -> dict:
    context_text = "\n\n".join(context_chunks)
    
    remedial_context = "None"
    if remedial_mode and history:
        last_attempt = history[-1]
        remedial_context = (
            f"Previous Level: {last_attempt.get('level')}. "
            f"Result: Incorrect answer chosen. "
            f"Diagnostic hint note to use: Simplify foundational terms."
        )
        
    prompt = prompts.PRACTICE_MODE_PROMPT.format(
        level=level,
        concept_name=concept_name,
        context_text=context_text,
        remedial_mode=str(remedial_mode),
        remedial_context=remedial_context
    )
    return call_groq_json(prompt)

def generate_descriptive_question(concept_name: str, context_chunks: list) -> dict:
    context_text = "\n\n".join(context_chunks)
    prompt = prompts.DESCRIPTIVE_QUESTION_PROMPT.format(concept_name=concept_name, context_text=context_text)
    return call_groq_json(prompt)

def generate_teacher_report(history: list, weak_concepts: list, strong_concepts: list) -> dict:
    history_trace = json.dumps(history, indent=2)
    prompt = prompts.TEACHER_REPORT_PROMPT.format(
        history_trace=history_trace,
        weak_concepts=", ".join(weak_concepts),
        strong_concepts=", ".join(strong_concepts)
    )
    return call_groq_json(prompt)
def extract_concepts(text_chunks: list, subject: str) -> list:
    """
    Extracts core structural concepts dynamically from the provided text chunks 
    using Groq's JSON formatting capability.
    """
    # Join the first few chunks to avoid hitting context token ceilings while preserving context accuracy
    corpus_sample = "\n\n".join(text_chunks[:4]) if text_chunks else "No content available."
    
    prompt = prompts.CONCEPT_EXTRACTION_PROMPT.format(
        subject=subject,
        corpus_sample=corpus_sample
    )
    
    result = call_groq_json(prompt)
    
    # Return the clean list of concepts, fallback to a sensible default if parsing encounters issues
    if "concepts" in result and isinstance(result["concepts"], list):
        return result["concepts"]
        
    # Hard fallback list based on common domains if something breaks
    if "os" in subject.lower():
        return ["Process Management", "CPU Scheduling", "Deadlocks", "Memory Management", "Virtual Memory"]
    return ["ER Modeling", "Normalization", "ACID Transactions", "Concurrency Control", "Indexing & Hashing"]