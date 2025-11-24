import pandas as pd
import numpy as np
import re
from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import math

def load_rubric_from_excel(path: str) -> pd.DataFrame:
    """
    Load rubric Excel and normalize expected columns.
    Expected columns (case-insensitive): Criterion, Description, Keywords, Weight, MinWords, MaxWords, MaxScore
    If MaxScore missing, default to 10 per criterion.
    """
    df = pd.read_excel(path)
    # Normalize column names to lowercase keys mapping
    col_map = {c.lower(): c for c in df.columns}
    def get(colname, default_series):
        return df[col_map[colname]] if colname in col_map else default_series

    n = len(df)
    rubric = pd.DataFrame()
    rubric['criterion'] = get('criterion', df.iloc[:,0])
    rubric['description'] = get('description', pd.Series([""]*n))
    rubric['keywords'] = get('keywords', pd.Series([""]*n)).fillna("")
    rubric['weight'] = get('weight', pd.Series([1.0]*n)).fillna(1.0).astype(float)
    rubric['minwords'] = get('minwords', pd.Series([0]*n)).fillna(0).astype(float)
    rubric['maxwords'] = get('maxwords', pd.Series([1e9]*n)).fillna(1e9).astype(float)
    rubric['max_score'] = get('maxscore', pd.Series([10]*n)).fillna(10).astype(float)
    # fallback if different naming like Max Score, Max_Score etc.
    if 'max_score' not in rubric:
        rubric['max_score'] = 10
    return rubric

def tokenize(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())

def keyword_presence_score(transcript: str, keywords: str) -> (float, List[str]):
    if not keywords or str(keywords).strip()=="":
        return 1.0, []
    words = set(tokenize(transcript))
    # parse keywords by comma/semicolon or newline
    kws = [k.strip().lower() for k in re.split(r'[;,|\n]', str(keywords)) if k.strip()]
    found = [k for k in kws if all(tok in words for tok in tokenize(k))]
    frac = len(found)/len(kws) if kws else 1.0
    return frac, found

def length_score(transcript: str, minw: float, maxw: float) -> float:
    n = len(tokenize(transcript))
    if minw<=n<=maxw:
        return 1.0
    if n < minw:
        return max(0.0, n / (minw if minw>0 else 1))
    else:
        if n <= 2*maxw:
            return max(0.0, (2*maxw - n) / maxw)
        return 0.0

def semantic_similarity_score(a: str, b: str) -> float:
    if not b or str(b).strip()=="":
        return 1.0
    try:
        vect = TfidfVectorizer().fit_transform([a,b])
        cs = cosine_similarity(vect[0], vect[1])[0][0]
        return float(cs)
    except Exception:
        return 0.0

def evaluate_transcript(transcript: str, rubric_df: pd.DataFrame) -> Dict:
    per_criteria = []
    total_weight = rubric_df['weight'].sum() if 'weight' in rubric_df else len(rubric_df)
    overall_RAW = 0.0
    for _, row in rubric_df.iterrows():
        crit = str(row['criterion'])
        desc = str(row.get('description','') or '')
        keywords = str(row.get('keywords','') or '')
        weight = float(row.get('weight',1.0))
        minw = float(row.get('minwords',0))
        maxw = float(row.get('maxwords',1e9))
        max_score = float(row.get('max_score',10))

        kw_frac, found_kws = keyword_presence_score(transcript, keywords)
        len_sc = length_score(transcript, minw, maxw)
        sem_sim = semantic_similarity_score(transcript, desc)

        combined = 0.25*kw_frac + 0.5*sem_sim + 0.25*len_sc
        crit_score = combined * max_score

        per = {
            "criterion": crit,
            "description": desc,
            "weight": weight,
            "max_score": max_score,
            "score": crit_score,
            "found_keywords": found_kws,
            "keyword_fraction": kw_frac,
            "length_score": len_sc,
            "similarity": sem_sim,
            "feedback": ""
        }
        fb = []
        if found_kws:
            fb.append(f"Found keywords: {', '.join(found_kws)}.")
        else:
            if keywords.strip():
                fb.append("No rubric keywords detected.")
        if len_sc < 0.9:
            fb.append("Transcript length outside suggested range.")
        if sem_sim < 0.45:
            fb.append("Low semantic similarity to rubric description.")
        per['feedback'] = " ".join(fb)

        per_criteria.append(per)
        overall_RAW += (crit_score * weight)

    max_raw = (rubric_df['max_score'] * rubric_df['weight']).sum()
    overall_score = (overall_RAW / max_raw) * 100 if max_raw>0 else 0.0

    return {
        "overall_score": float(overall_score),
        "per_criteria": per_criteria,
        "words": len(tokenize(transcript))
    }


# Rule-based "AI-like" summary
def split_into_sentences(text: str) -> List[str]:
    # naive sentence splitter on .!? newlines
    parts = re.split(r'(?<=[.!?\n])\s+', text.strip())
    sentences = [p.strip() for p in parts if len(p.strip())>0]
    return sentences

def sentence_importance_scores(transcript: str) -> List[float]:
    sentences = split_into_sentences(transcript)
    if not sentences:
        return []
    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        X = vectorizer.fit_transform(sentences)
        # Score sentence importance by sum of tf-idf weights
        scores = X.sum(axis=1).A1.tolist()
        # normalize
        if max(scores) > 0:
            scores = [s / max(scores) for s in scores]
        return scores
    except Exception:
        # fallback
        scores = [len(s) for s in sentences]
        if max(scores) > 0:
            scores = [s/max(scores) for s in scores]
        return scores

def generate_rule_based_summary(transcript: str, max_sentences: int = 3) -> str:
    transcript = transcript.strip()
    if not transcript:
        return "No transcript provided."

    sentences = split_into_sentences(transcript)
    if not sentences:
        return transcript[:400]

    scores = sentence_importance_scores(transcript)
    # pick top sentences
    indexed = list(enumerate(scores))
    indexed_sorted = sorted(indexed, key=lambda x: x[1], reverse=True)
    top_idxs = sorted([i for i,_ in indexed_sorted[:max_sentences]])
    summary_sentences = [sentences[i] for i in top_idxs]
    short_summary = " ".join(summary_sentences)
    # create a small polished summary using heuristics
    lower = transcript.lower()
    name = None
    m = re.search(r"\b(my name is|i am|i'm)\s+([A-Z]?[a-z]+(?:\s+[A-Z]?[a-z]+)?)", transcript)
    if m:
        name = m.group(2)
    # find phrases for goals/background
    goals = None
    gm = re.search(r"(goal|aspire|want to|aim to|hope to|interested in)\s+([^.]{1,120})", lower)
    if gm:
        goals = gm.group(2).strip()

    # generate template style summary
    lines = []
    if name:
        lines.append(f"{name} introduces themselves confidently.")
    # add the most important content
    lines.append(short_summary)
    if goals:
        lines.append("They mention goals or aspirations: " + (goals if len(goals)<120 else goals[:120]+"..."))
    # final polishing
    summary = " ".join(lines)
    # trim
    if len(summary) > 600:
        summary = summary[:600].rsplit(" ",1)[0] + "..."
    return summary


# Missing element detector
def detect_missing_elements(transcript: str) -> dict:
    text = transcript.lower()
    elements = {
        "name": bool(re.search(r"\b(my name is|i am|i'm)\b", text)),
        "background": bool(re.search(r"\b(from|born in|raised in|originally from)\b", text)),
        "education": bool(re.search(r"\b(student|pursuing|studying|degree|bachelor|master|college|university)\b", text)),
        "interests": bool(re.search(r"\b(i like|interested in|my interests|i enjoy|hobbies)\b", text)),
        "skills": bool(re.search(r"\b(skill|expertise|proficient|familiar with|experience)\b", text)),
        "goals": bool(re.search(r"\b(goal|aspire|aim|hope|want to|future)\b", text)),
        "motivation": bool(re.search(r"\b(because|reason|motivated|passion|drive)\b", text))
    }
    present = [k for k,v in elements.items() if v]
    missing = [k for k,v in elements.items() if not v]
    return {"present": present, "missing": missing}
