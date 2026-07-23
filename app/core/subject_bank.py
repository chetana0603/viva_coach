"""
subject_bank.py
---------------
Stable syllabus backbone for Subject Viva.

Gives concept NAMES per subject so questions stay syllabus-aligned instead of
random. Backend notes (subject_loader) supply the material-specific grounding;
this file guarantees coverage and provides a small offline question bank used as
a fallback when no LLM key is configured.
"""

SUBJECTS = {
    "DBMS": {
        "display": "Database Management Systems",
        "concepts": [
            "Relational Model and Keys",
            "Normalization and Functional Dependencies",
            "SQL Queries and Joins",
            "Transactions and ACID Properties",
            "Indexing and Query Performance",
            "ER Model and Schema Design",
        ],
    },
    "OS": {
        "display": "Operating Systems",
        "concepts": [
            "Processes and Threads",
            "CPU Scheduling",
            "Virtual Memory and Paging",
            "Deadlocks",
            "Process Synchronization",
            "File Systems",
        ],
    },
}


def list_subjects():
    return list(SUBJECTS.keys())


def get_concepts(subject: str):
    return SUBJECTS.get(subject, {}).get("concepts", [])


def get_display_name(subject: str):
    return SUBJECTS.get(subject, {}).get("display", subject)


# ---------------------------------------------------------------------------
# Offline leveled MCQ bank (fallback when no LLM is configured).
# Each entry: level, question, options (list), answer (index), explanation.
# Levels: 0 Recognition, 1 Purpose, 2 Relationship, 3 Application, 4 What-if,
#         5 Design Reasoning.
# ---------------------------------------------------------------------------

OFFLINE_MCQS = {
    "Normalization and Functional Dependencies": [
        {"level": 0, "question": "What does normalization primarily organize in a database?",
         "options": ["Table data to reduce redundancy", "User passwords", "Network packets", "Screen layouts"],
         "answer": 0,
         "explanation": "Normalization organizes tables to reduce redundancy and improve consistency."},
        {"level": 1, "question": "Why is normalization used?",
         "options": ["To make queries look complex", "To prevent insertion, update and deletion anomalies",
                     "To increase disk usage", "To encrypt data"],
         "answer": 1,
         "explanation": "Its main purpose is preventing data anomalies caused by redundancy."},
        {"level": 2, "question": "How do functional dependencies relate to normalization?",
         "options": ["They are unrelated", "They decide how tables are decomposed",
                     "They store backups", "They index columns"],
         "answer": 1,
         "explanation": "Functional dependencies show how attributes depend on each other and guide decomposition."},
        {"level": 3, "question": "Where is normalization applied during database design?",
         "options": ["When designing table structure and relationships", "During user login",
                     "While printing reports", "When compiling code"],
         "answer": 0,
         "explanation": "It is applied while structuring tables and defining how they relate."},
        {"level": 4, "question": "What happens if tables are poorly normalized?",
         "options": ["Faster queries always", "Redundancy and update anomalies increase",
                     "Data becomes encrypted", "Indexes disappear"],
         "answer": 1,
         "explanation": "Poor normalization leads to redundant data and anomalies during updates."},
        {"level": 5, "question": "Why not always fully normalize every database?",
         "options": ["Full normalization is illegal", "Excessive joins can hurt read performance",
                     "It deletes data", "Normalization is optional syntax"],
         "answer": 1,
         "explanation": "Highly normalized schemas need many joins, so denormalization is sometimes a deliberate trade-off for speed."},
        {"level": 1, "question": "Which problem does normalization mainly prevent?",
         "options": ["Data redundancy and anomalies", "Slow internet", "Weak passwords", "UI bugs"],
         "answer": 0,
         "explanation": "Remedial: normalization's core benefit is removing redundancy and the anomalies it causes."},
    ],
    "Relational Model and Keys": [
        {"level": 0, "question": "In the relational model, data is stored as?",
         "options": ["Tables (relations)", "Trees", "Graphs only", "Plain images"],
         "answer": 0, "explanation": "The relational model represents data as tables called relations."},
        {"level": 1, "question": "Why is a primary key used?",
         "options": ["To uniquely identify each row", "To style the table", "To slow queries", "To hide columns"],
         "answer": 0, "explanation": "A primary key uniquely identifies each tuple in a relation."},
        {"level": 2, "question": "What is the relationship between a foreign key and a primary key?",
         "options": ["No relationship", "A foreign key references a primary key in another table",
                     "They are the same column", "Foreign keys replace indexes"],
         "answer": 1, "explanation": "A foreign key links to the primary key of another relation to enforce referential integrity."},
        {"level": 3, "question": "Where would you use a candidate key?",
         "options": ["As a possible unique identifier for rows", "As a page title",
                     "For network routing", "For encryption keys"],
         "answer": 0, "explanation": "A candidate key is any minimal attribute set that can uniquely identify rows; one becomes the primary key."},
        {"level": 4, "question": "What happens if a table has no primary key?",
         "options": ["Nothing changes", "Duplicate/ambiguous rows and integrity issues can occur",
                     "The database explodes", "Queries become faster"],
         "answer": 1, "explanation": "Without a key, rows can be duplicated and referential integrity cannot be enforced reliably."},
        {"level": 5, "question": "Why might you choose a surrogate key over a natural key?",
         "options": ["Surrogate keys are random noise", "Natural keys can change or be non-unique over time",
                     "Natural keys are illegal", "Surrogate keys delete data"],
         "answer": 1, "explanation": "Natural keys (e.g., email) can change; a stable surrogate key avoids cascading updates."},
    ],
    "CPU Scheduling": [
        {"level": 0, "question": "CPU scheduling decides?",
         "options": ["Which process runs next on the CPU", "How to format disks",
                     "The screen resolution", "The network speed"],
         "answer": 0, "explanation": "Scheduling selects which ready process gets the CPU next."},
        {"level": 1, "question": "Why is CPU scheduling needed?",
         "options": ["To maximize CPU utilization and fairness", "To increase power usage",
                     "To slow the system", "To encrypt processes"],
         "answer": 0, "explanation": "It improves utilization, throughput, and fairness among processes."},
        {"level": 2, "question": "How does Round Robin differ from FCFS?",
         "options": ["They are identical", "Round Robin uses time quanta and preemption; FCFS does not",
                     "FCFS uses quanta", "Round Robin ignores order"],
         "answer": 1, "explanation": "Round Robin preempts processes after a time quantum; FCFS runs to completion in arrival order."},
        {"level": 3, "question": "Where is Shortest Job First best applied?",
         "options": ["When burst times are known and you want minimal average wait",
                     "For real-time random tasks", "For disk formatting", "Only for I/O"],
         "answer": 0, "explanation": "SJF minimizes average waiting time when job burst lengths are known."},
        {"level": 4, "question": "What happens with a very small Round Robin time quantum?",
         "options": ["No effect", "Excessive context-switch overhead", "Deadlock always", "Memory doubles"],
         "answer": 1, "explanation": "Too-small quanta cause frequent context switches, wasting CPU time."},
        {"level": 5, "question": "Why choose a multilevel feedback queue?",
         "options": ["It is simplest", "It adapts priorities to balance short and long jobs",
                     "It removes scheduling", "It only runs one process"],
         "answer": 1, "explanation": "MLFQ dynamically adjusts priority so interactive and CPU-bound jobs are both handled well."},
    ],
    "Virtual Memory and Paging": [
        {"level": 0, "question": "Paging divides memory into?",
         "options": ["Fixed-size pages and frames", "Random blobs", "Single big block", "Files only"],
         "answer": 0, "explanation": "Paging splits logical memory into pages and physical memory into equal-size frames."},
        {"level": 1, "question": "Why is virtual memory used?",
         "options": ["To run programs larger than physical RAM", "To slow programs",
                     "To delete files", "To disable the CPU"],
         "answer": 0, "explanation": "Virtual memory lets processes use more address space than the available physical RAM."},
        {"level": 2, "question": "What is the relationship between a page fault and the TLB?",
         "options": ["None", "A TLB miss/absent page can trigger a page fault to load the page",
                     "TLB stores files", "Page faults format disks"],
         "answer": 1, "explanation": "The TLB caches page-table entries; a missing mapping/page can cause a page fault that loads the page from disk."},
        {"level": 3, "question": "Where does the page table live and get used?",
         "options": ["It maps virtual pages to physical frames during address translation",
                     "It stores user passwords", "It schedules the CPU", "It renders the UI"],
         "answer": 0, "explanation": "The page table translates virtual addresses to physical frame addresses."},
        {"level": 4, "question": "What happens when page faults occur too frequently?",
         "options": ["Faster execution", "Thrashing degrades performance", "Nothing", "More RAM appears"],
         "answer": 1, "explanation": "Excessive paging (thrashing) means the system spends most time swapping instead of executing."},
        {"level": 5, "question": "Why choose a larger page size?",
         "options": ["It always wins", "Fewer TLB entries needed but more internal fragmentation",
                     "It removes paging", "It disables memory"],
         "answer": 1, "explanation": "Larger pages reduce page-table/TLB overhead but waste more memory to internal fragmentation — a trade-off."},
    ],
}


def get_offline_mcqs(concept: str):
    """Return offline MCQs for a concept, or a generic template set if absent."""
    return OFFLINE_MCQS.get(concept, [])
