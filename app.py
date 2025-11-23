import streamlit as st
import pandas as pd
from evaluation_logic import evaluate_transcript, load_rubric_from_excel

st.set_page_config(page_title="Student Intro Evaluator", layout="centered")

st.title("Student Spoken Introduction Evaluator")
st.markdown("Upload or paste a transcript and get a rubric-based score (0-100).")

# Paths (defaults to uploaded files)
DEFAULT_RUBRIC_PATH = "/mnt/data/Case study for interns.xlsx"

st.sidebar.header("Settings")
rubric_path = st.sidebar.text_input("Rubric Excel path", value=DEFAULT_RUBRIC_PATH)

rubric = None
try:
    rubric = load_rubric_from_excel(rubric_path)
except Exception as e:
    st.sidebar.error(f"Failed to load rubric: {e}")

st.header("Input transcript")
input_mode = st.radio("Input mode", ("Paste text", "Upload .txt file"))
transcript_text = ""
if input_mode == "Paste text":
    transcript_text = st.text_area("Paste transcript here", height=250)
else:
    uploaded_file = st.file_uploader("Upload transcript (.txt)", type=["txt"])
    if uploaded_file is not None:
        transcript_text = uploaded_file.read().decode("utf-8")

if st.button("Score"):
    if not transcript_text:
        st.error("Please provide a transcript.")
    elif rubric is None:
        st.error("Rubric not loaded. Check the path in the sidebar.")
    else:
        with st.spinner("Evaluating..."):
            result = evaluate_transcript(transcript_text, rubric)
        overall = result["overall_score"]
        per_criteria = result["per_criteria"]

        st.metric("Overall score (0-100)", f"{overall:.1f}")

        st.subheader("Per-criterion breakdown")
        for c in per_criteria:
            st.write(f"**{c['criterion']}** — Score: {c['score']:.1f} / {c['max_score']}")
            st.write(f"- Weight: {c.get('weight', 'N/A')}")
            st.write(f"- Keywords found: {', '.join(c.get('found_keywords', [])) or 'None'}")
            st.write(f"- Semantic similarity: {c.get('similarity', 0):.3f}")
            st.write(f"- Feedback: {c.get('feedback','')}")
            st.write("---")

        st.subheader("JSON output")
        st.json(result)
