import streamlit as st
from evaluation_logic import (
    load_rubric_from_excel,
    evaluate_transcript,
    generate_rule_based_summary,
    detect_missing_elements
)
import os
import json

st.set_page_config(page_title="introsense - Student Intro Evaluator", layout="wide")

st.markdown("# 🎓 Introsense")
st.markdown("**AI-like summary & rubric-based scoring for student introductions**")
st.markdown("---")

# Default paths
DEFAULT_RUBRIC_PATH = "Case study for interns.xlsx"
DEFAULT_SAMPLE_TRANSCRIPT = "Sample text for case study.txt"
DEFAULT_CASESTUDY_PDF = "Nirmaan AI intern Case study instructions.pdf"

st.sidebar.header("Files & Settings")
rubric_path = st.sidebar.text_input("Rubric Excel path", value=DEFAULT_RUBRIC_PATH)
use_sample = st.sidebar.checkbox("Use uploaded sample transcript", value=True)
show_json = st.sidebar.checkbox("Show JSON output (developer view)", value=False)

st.header("Input Transcript")
if use_sample:
    st.write(f"*Using sample transcript from* `{DEFAULT_SAMPLE_TRANSCRIPT}`")
    try:
        with open(DEFAULT_SAMPLE_TRANSCRIPT, "r", encoding="utf-8") as f:
            transcript_text = f.read()
    except Exception as e:
        st.error(f"Could not read sample transcript: {e}")
        transcript_text = st.text_area("Or paste transcript here", height=250)
else:
    transcript_text = st.text_area("Paste transcript here", height=300)

uploaded = st.file_uploader("Or upload a .txt transcript file", type=["txt"])
if uploaded is not None:
    transcript_text = uploaded.read().decode("utf-8")

st.markdown("---")
if st.button("Evaluate"):
    if not transcript_text or transcript_text.strip()=="":
        st.error("Please provide transcript text (paste or upload).")
    else:
        # Load rubric
        try:
            rubric_df = load_rubric_from_excel(rubric_path)
        except Exception as e:
            st.error(f"Failed to load rubric from `{rubric_path}`: {e}")
            st.stop()

        # Evaluate
        with st.spinner("Scoring transcript..."):
            result = evaluate_transcript(transcript_text, rubric_df)

        # Show overall score
        col1, col2 = st.columns([1,2])
        with col1:
            st.metric("Overall score (0-100)", f"{result['overall_score']:.1f}")
            st.write(f"Words: {result.get('words',0)}")
        with col2:
            # simple bar chart for criteria
            crits = [c['criterion'] for c in result['per_criteria']]
            scores = [c['score'] for c in result['per_criteria']]
            maxs = [c['max_score'] for c in result['per_criteria']]
            # normalize to 0-1 for plotting
            normalized = [s/m if m>0 else 0 for s,m in zip(scores,maxs)]
            st.bar_chart({ "score_fraction": normalized })

        st.subheader("Per-criterion breakdown")
        for c in result['per_criteria']:
            st.markdown(f"**{c['criterion']}** — {c['score']:.1f} / {c['max_score']}")
            st.write(f"- Weight: {c.get('weight','N/A')}")
            if c.get('found_keywords'):
                st.write(f"- Keywords found: {', '.join(c.get('found_keywords'))}")
            st.write(f"- Feedback: {c.get('feedback','')}")
            st.write("")

        st.subheader("✨ Rule-based AI Summary")
        summary = generate_rule_based_summary(transcript_text)
        st.write(summary)

        st.subheader("🧩 Missing Elements Detector")
        missing = detect_missing_elements(transcript_text)
        st.write("**Present:**", ", ".join(missing["present"]) or "None detected")
        st.write("**Missing:**", ", ".join(missing["missing"]) or "None")
        if missing["missing"]:
            st.info("To improve the introduction, consider adding: " + ", ".join(missing["missing"]))
        else:
            st.success("Great! Your introduction covers the important elements.")

        if show_json:
            st.subheader("JSON Output")
            st.json(result)

st.markdown("---")
st.caption(f"Rubric file path (default): `{DEFAULT_RUBRIC_PATH}`")
st.caption(f"Sample transcript path (default): `{DEFAULT_SAMPLE_TRANSCRIPT}`")
st.caption(f"Case study PDF (uploaded): `{DEFAULT_CASESTUDY_PDF}`")
