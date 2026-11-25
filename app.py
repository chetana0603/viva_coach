# app.py
import streamlit as st

st.set_page_config(
    page_title="AI-Based Adaptive Viva Preparation Engine", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

import core_engine
import scoring
import integrity

# --- GLOBAL STYLING CORES ---
st.markdown("""
    <style>
        .reportview-container .main .block-container { max-width: 95%; padding-top: 1.5rem; }
        .stButton>button { width: 100%; border-radius: 6px; height: 3em; font-weight: bold; }
        .metric-card { background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #4b7bff; margin-bottom: 15px; }
        .flag-card { background-color: #fff0f0; padding: 15px; border-radius: 8px; border-left: 5px solid #ff4b4b; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- WORKSPACE STATE SYSTEM REGISTER ---
init_states = {
    "uploaded_text": "",
    "extracted_concepts": [],
    "current_concept_idx": 0,
    "current_card_text": "",
    "practice_question": None,
    "user_answer_submitted": False,
    "selected_option": None,
    "adaptive_level": 0, 
    "evaluation_history": [],
    "question_start_time": None,
    "descriptive_question": None,
    "descriptive_submitted": False,
    "descriptive_answer": "",
    "demo_paste_checkbox": False
}
for key, val in init_states.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- SIDEBAR CONTROL PIPELINE ---
st.sidebar.title("🎯 Control Center")
st.sidebar.caption("Prepare for subject and project viva using notes, uploaded materials, adaptive questions, and readiness reports.")
st.sidebar.markdown("---")

viva_type = st.sidebar.radio("Select Viva Type:", ["Subject Viva", "Project Viva"])

if viva_type == "Subject Viva":
    subject_choice = st.sidebar.selectbox("Select Subject:", ["DBMS", "Operating Systems"])
    uploaded_files = st.sidebar.file_uploader("Upload optional subject notes (PDF, TXT):", type=["pdf", "txt"], accept_multiple_files=True)
    trigger_action = st.sidebar.button("Initialize Subject Viva")
else:
    subject_choice = None
    uploaded_files = st.sidebar.file_uploader("Upload project material (PDF report, code files, SQL):", type=["pdf", "txt", "py", "java", "sql", "c", "cpp"], accept_multiple_files=True)
    trigger_action = st.sidebar.button("Analyze Project Material")

# --- INITIALIZATION LOGIC ---
if trigger_action:
    with st.spinner("Processing technical materials..."):
        # Handle file extracts or fall back to pre-defined matrices automatically
        if uploaded_files:
            parsed_corpus = core_engine.process_uploaded_files(uploaded_files)
        else:
            parsed_corpus = ""
            
        st.session_state.uploaded_text = parsed_corpus
        concepts = core_engine.extract_concepts(parsed_corpus, subject=subject_choice)
        
        st.session_state.extracted_concepts = concepts
        st.session_state.current_concept_idx = 0
        st.session_state.current_card_text = ""
        st.session_state.practice_question = None
        st.session_state.descriptive_question = None
        st.session_state.descriptive_submitted = False
        st.session_state.adaptive_level = 0
        st.session_state.user_answer_submitted = False
        st.session_state.evaluation_history = []
        st.success(f"Successfully loaded {len(concepts)} concepts! Get started in the tabs below.")

# --- COCKPIT INTERFACE TAB SETUP ---
st.title("🛡️ Contextual Adaptive Viva Cockpit")
st.markdown("---")

if not st.session_state.extracted_concepts:
    st.info("💡 App workspace ready. Populate your material profile using the controller sidebar to generate active conceptual traces.")
else:
    tab_options = ["📚 Learn Mode", "⚔️ Practice Mode", "📊 Report Mode"]
    chosen_tab = st.radio("Navigation Workspace Router:", tab_options, horizontal=True, label_visibility="collapsed")
    st.markdown("---")

    concepts_list = st.session_state.extracted_concepts
    idx = st.session_state.current_concept_idx
    active_concept = concepts_list[idx]

    # ==================== TAB 1: LEARN MODE ====================
    if chosen_tab == "📚 Learn Mode":
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("Syllabus Concept Index")
            for i, c in enumerate(concepts_list):
                label = f"🔥 {c['name']} (Active)" if i == idx else f"📌 {c['name']}"
                if st.button(label, key=f"sel_concept_{i}"):
                    st.session_state.current_concept_idx = i
                    st.session_state.current_card_text = ""
                    st.session_state.practice_question = None
                    st.session_state.descriptive_question = None
                    st.session_state.descriptive_submitted = False
                    st.session_state.user_answer_submitted = False
                    st.session_state.adaptive_level = 0
                    st.rerun()
                    
            st.markdown("---")
            st.caption(f"**Classification Context**: {active_concept.get('type', 'Core Framework')}")
            st.write(f"**Relevance**: {active_concept.get('reason', '')}")

        with col2:
            st.subheader(f"Study Card: {active_concept['name']}")
            if not st.session_state.current_card_text:
                with st.spinner("Generating short study notes..."):
                    st.session_state.current_card_text = core_engine.generate_learn_card(active_concept, st.session_state.uploaded_text)
            st.markdown(st.session_state.current_card_text)

    # ==================== TAB 2: ADAPTIVE PRACTICE MODE ====================
    elif chosen_tab == "⚔️ Practice Mode":
        st.subheader("Adaptive Multi-Tier Assessment Engine")
        
        # Decide if running MCQ stages or the single final Descriptive demo stage
        mcq_attempts_on_concept = [h for h in st.session_state.evaluation_history if h["concept"] == active_concept["name"] and "is_correct" in h]
        
        # We transition to descriptive after completing 3 MCQ scaling checks on this concept
        run_descriptive_stage = len(mcq_attempts_on_concept) >= 3
        
        if not run_descriptive_stage:
            # --- MCQ WORKFLOW ENGINE ---
            current_lvl = st.session_state.adaptive_level
            level_name = core_engine.LEVELS[current_lvl]["name"]
            st.markdown(f"**Current Topic**: `{active_concept['name']}` | **Adaptive Level**: `Level {current_lvl} ({level_name})` | **Progress**: `{len(mcq_attempts_on_concept)}/3 MCQ Checks Completed`")
            
            if st.session_state.practice_question is None:
                st.session_state.practice_question = core_engine.generate_mcq_question(
                    active_concept['name'], st.session_state.uploaded_text, current_lvl
                )
                st.session_state.user_answer_submitted = False
                st.session_state.selected_option = None
                st.session_state.question_start_time = integrity.start_question_timer()

            q = st.session_state.practice_question
            st.info(f"**Question**: {q['question']}")
            
            # Submission execution block
            with st.form(key="mcq_submit_form"):
                ans = st.radio("Select your answer:", q["options"], index=None)
                
                c_btn, n_btn = st.columns(2)
                with c_btn:
                    check_submitted = st.form_submit_button("Check Answer")
                with n_btn:
                    next_disabled = not st.session_state.user_answer_submitted
                    next_submitted = st.form_submit_button("Next Question", disabled=next_disabled)
            
            if check_submitted and not st.session_state.user_answer_submitted:
                if ans is None:
                    st.warning("Please select an answer option first.")
                else:
                    # Capture exact telemetry instantly upon click
                    elapsed_time = integrity.calculate_response_time(st.session_state.question_start_time)
                    choices = q["options"]
                    sel_idx = choices.index(ans)
                    correct_idx = int(q["correct_index"])
                    is_correct = (sel_idx == correct_idx)
                    
                    flags = integrity.detect_telemetry_flags(elapsed_time, ans, is_descriptive=False)
                    
                    # Lock input answers
                    st.session_state.user_answer_submitted = True
                    st.session_state.selected_option = ans
                    
                    # Store detailed record right into evaluation history
                    st.session_state.evaluation_history.append({
                        "concept": active_concept["name"],
                        "level": current_lvl,
                        "question": q["question"],
                        "selected_answer": ans,
                        "correct_answer": choices[correct_idx],
                        "is_correct": is_correct,
                        "explanation": q["explanation"],
                        "response_time": elapsed_time,
                        "integrity_flags": flags
                    })
                    st.rerun()

            if st.session_state.user_answer_submitted:
                record = st.session_state.evaluation_history[-1]
                if record["is_correct"]:
                    st.success("🎯 **Correct!** Adaptive tracking metrics verified successfully.")
                else:
                    st.error(f"❌ **Incorrect.** The correct choice was: **{record['correct_answer']}**")
                
                st.markdown(f"**Explanation**: {record['explanation']}")
                st.caption(f"Telemetry metrics recorded: `Response Time: {record['response_time']}s` | `Active Flags: {len(record['integrity_flags'])}`")
                
                # Dynamic Level Adaptation Calculations
                if record["is_correct"]:
                    calculated_next_level = min(5, current_lvl + 1)
                else:
                    calculated_next_level = max(0, current_lvl - 1)
                    
                st.info(f"Click 'Next Question' to save adjustments and load **Level {calculated_next_level}** criteria.")
                
                if next_submitted:
                    st.session_state.adaptive_level = calculated_next_level
                    st.session_state.practice_question = None
                    st.session_state.user_answer_submitted = False
                    st.rerun()
                    
        else:
            # --- FINAL DESCRIPTIVE DEMO STAGE ---
            st.markdown(f"**Current Topic**: `{active_concept['name']}` | 🛡️ **Final Descriptive Validation Stage** (Integrity Demo)")
            st.warning("Note: This open-ended section validates response speeds and text submission patterns for evaluations.")
            
            if st.session_state.descriptive_question is None:
                st.session_state.descriptive_question = core_engine.generate_descriptive_question(
                    active_concept["name"], st.session_state.uploaded_text
                )
                st.session_state.descriptive_submitted = False
                st.session_state.descriptive_answer = ""
                st.session_state.question_start_time = integrity.start_question_timer()
                
            dq = st.session_state.descriptive_question
            st.info(f"**Descriptive Challenge**: {dq['question']}")
            
            user_text = st.text_area("Type your explanation response here (3-4 lines):", key="desc_input_area")
            
            # Explicit parameters for simulated integrity testing
            st.session_state.demo_paste_checkbox = st.checkbox("Demo: Simulate text copy-paste event flag")
            
            if st.button("Submit Descriptive Response") and not st.session_state.descriptive_submitted:
                if len(user_text.strip()) < 10:
                    st.warning("Please type a valid response explanation first.")
                else:
                    elapsed_time = integrity.calculate_response_time(st.session_state.question_start_time)
                    flags = integrity.detect_telemetry_flags(
                        elapsed_time, user_text, is_descriptive=True, simulated_paste=st.session_state.demo_paste_checkbox
                    )
                    
                    st.session_state.descriptive_submitted = True
                    st.session_state.descriptive_answer = user_text
                    
                    # Append descriptive result track matrix 
                    st.session_state.evaluation_history.append({
                        "concept": active_concept["name"],
                        "level": "Descriptive",
                        "question": dq["question"],
                        "selected_answer": user_text,
                        "evaluation_criteria": dq["evaluation_criteria"],
                        "response_time": elapsed_time,
                        "integrity_flags": flags
                    })
                    st.success("Descriptive response saved! View analysis inside the Analytics Hub.")
                    
            if st.session_state.descriptive_submitted:
                st.markdown("### Evaluator Grading Benchmarks")
                st.markdown(f"**Target Evaluation Criteria**: {dq['evaluation_criteria']}")
                if st.button("Reset Topic Tracking to Start Over"):
                    st.session_state.practice_question = None
                    st.session_state.descriptive_question = None
                    st.session_state.descriptive_submitted = False
                    st.session_state.adaptive_level = 0
                    st.session_state.user_answer_submitted = False
                    # Clear out items specifically matching current concept to restart sequence loop
                    st.session_state.evaluation_history = [h for h in st.session_state.evaluation_history if h["concept"] != active_concept["name"]]
                    st.rerun()

    # ==================== TAB 3: ANALYTICS HUB & REPORT MODE ====================
    elif chosen_tab == "📊 Report Mode":
        history = st.session_state.evaluation_history
        
        if not history:
            st.info("No assessment metrics generated yet. Complete question parameters inside 'Practice Mode' to compile analytics reports.")
        else:
            readiness_score = scoring.calculate_readiness_score(history)
            label, color_theme = scoring.generate_readiness_label(readiness_score)
            
            # Display score dashboard metrics
            st.subheader("Student Preparedness Dashboard")
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                st.metric("Overall Viva Readiness Score", f"{readiness_score}%")
            with r_col2:
                st.markdown(f"<div class='metric-card'><h4>Status Flag: <span style='color:{color_theme};'>{label}</span></h4><p>Continuous system analytics map updated synchronously.</p></div>", unsafe_allow_html=True)
                
            st.markdown("---")
            
            # Concept distribution and level diagnostics split layouts
            col_an1, col_an2 = st.columns(2)
            with col_an1:
                st.markdown("### Topic Mastery Performance")
                weak_c, strong_c = scoring.detect_weak_and_strong_concepts(history)
                if strong_c:
                    st.success(f"**Strong Areas**: {', '.join(strong_c)}")
                if weak_c:
                    st.error(f"**Weak / Target Revision Areas**: {', '.join(weak_c)}")
                else:
                    st.info("Keep practice scaling going to map weak area boundaries reliably.")
                    
            with col_an2:
                st.markdown("### Level-Wise Accuracy Trace")
                lvl_data = scoring.get_level_wise_analytics(history)
                for lvl, stats in lvl_data.items():
                    if stats["total"] > 0:
                        acc = round((stats["correct"] / stats["total"]) * 100)
                        st.markdown(f"- **Level {lvl} ({core_engine.LEVELS[lvl]['name']})**: `{acc}% Correct` ({stats['correct']}/{stats['total']} answers)")

            st.markdown("---")
            
            # --- TELEMETRY AND INTEGRITY LOG PANEL ---
            st.subheader("🛡️ Proctoring & Integrity Telemetry Log")
            total_flags, flag_logs = integrity.build_integrity_summary(history)
            
            if total_flags == 0:
                st.success("✅ Clean session profile verified. No anomalous telemetry markers observed inside viewport.")
            else:
                st.warning(f"⚠️ {total_flags} Suspicious Signals flagged by tracking logic parameters:")
                for log in flag_logs:
                    st.markdown(f"<div class='flag-card'><strong>Suspicious Indicator Flagged:</strong><br>{log}</div>", unsafe_allow_html=True)
                    
            st.markdown("---")
            
            # --- EVALUATOR CORES PANEL ---
            st.subheader("👨‍🏫 Internal Review Console (Teacher View)")
            st.caption("Custom evaluation support vectors provided for oral validation boards.")
            
            st.markdown("#### Dynamic Oral Follow-up Prompt Blueprint")
            weak_c_all, _ = scoring.detect_weak_and_strong_concepts(history)
            generated_questions = scoring.generate_teacher_followups(weak_c_all)
            for num, q_text in enumerate(generated_questions, 1):
                st.markdown(f"{num}. *{q_text}*")
                
            st.markdown("#### Historical Assessment Question Trace")
            for entry in history:
                is_mcq = "is_correct" in entry
                status_icon = "📝 Descriptive" if not is_mcq else ("✅ Right" if entry["is_correct"] else "❌ Fault")
                lvl_disp = f"Level {entry['level']}" if is_mcq else "Descriptive"
                
                with st.expander(f"{status_icon} | {entry['concept']} ({lvl_disp})"):
                    st.markdown(f"**Question**: {entry['question']}")
                    st.markdown(f"**Submitted Input**: {entry['selected_answer']}")
                    if is_mcq:
                        st.markdown(f"**Correct Target**: {entry['correct_answer']}")
                        st.markdown(f"**Justification**: {entry['explanation']}")
                    else:
                        st.markdown(f"**Grading Key Criteria**: {entry['evaluation_criteria']}")
                    st.caption(f"Telemetry tracking metrics: Response time latency {entry['response_time']}s")