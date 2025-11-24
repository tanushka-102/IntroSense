#IntroSense
Student Spoken Introduction Evaluator
------------------------------------
A Streamlit app that scores a student's self-introduction transcript using a rubric Excel.

Files:
- app.py : Streamlit frontend
- evaluation_logic.py : scoring functions
- requirements.txt
- Rubric file: /mnt/data/Case study for interns.xlsx (provided)
- Sample transcript: /mnt/data/Sample text for case study.txt. :contentReference[oaicite:2]{index=2}
- Case study instructions PDF: /mnt/data/Nirmaan AI intern Case study instructions.pdf. :contentReference[oaicite:3]{index=3}

Run locally:
1. Create a virtualenv, activate it.
2. pip install -r requirements.txt
3. streamlit run app.py
4. In the sidebar set rubric path if needed (default uses the uploaded Excel).

Scoring formula:
- For each rubric criterion:
  - keyword fraction (0-1)
  - length score (0-1) based on min/max words (if provided)
  - semantic similarity (0-1) between transcript and criterion description
- Combined per-criterion score = 0.2*keywords + 0.4*similarity + 0.4*length
- Per-criterion scaled by criterion max_score (from rubric)
- Overall score = weighted sum across criteria (weights from rubric) normalized to 0-100

Notes:
- The rubric Excel should contain columns like Criterion, Description, Keywords, Weight, MinWords, MaxWords, MaxScore. If columns differ, the loader will attempt to map sensibly; you can edit load_rubric_from_excel for custom column names.
