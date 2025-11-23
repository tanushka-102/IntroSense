import pandas as pd
import numpy as np
import re
from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

#for exception
try:
    from sentence_transformers import SentenceTransformer
    st_model = SentenceTransformer("all-MiniLM-L6-v2")
except Exception:
    st_model = None

def load_rubric_from_excel(path: str) -> pd.DataFrame:
    """
    Load rubric Excel and normalize expected columns.
    Expected columns (case-insensitive): Criterion, Description, Keywords, Weight, MinWords, MaxWords, MaxScore
    If MaxScore missing, default to 10 per criterion.
    """
    df = pd.read_excel(path)
    # normalize columns
    cols = {c.lower(): c for c in df.columns}
    def get(colname, default=None):
        return df[cols[colname]] if colname in cols else default

    rubric = pd.DataFrame()
    rubric['criterion'] = get('criterion', df.iloc[:,0])
    rubric['description'] = get('description', df.iloc[:,1] if df.shape[1]>1 else pd.Series([""]*len(df)))
    rubric['keywords'] = get('keywords', pd.Series([""]*len(df))).fillna("")
    rubric['weight'] = get('weight', pd.Series([1.0]*len(df))).fillna(1.0).astype(float)
    rubric['minwords'] = get('minwords', pd.Series([0]*len(df))).fillna(0).astype(float)
    rubric['maxwords'] = get('maxwords', pd.Series([1e9]*len(df))).fillna(1e9).astype(float)
    rubric['max_score'] = get('maxscore', pd.Series([10]*len(df))).fillna(10).astype(float)
    return rubric

def tokenize(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())

def keyword_presence_score(transcript: str, keywords: str) -> (float, List[str]):
    """
    Return fraction of keywords found (0-1) and list of found keywords.
    keywords: comma-separated string or space-separated.
    """
    if not keywords or str(keywords).strip()=="":
        return 1.0, []  # no keywords specified -> full score for keyword part
    words = set(tokenize(transcript))
    # parse keywords
    kws = [k.strip().lower() for k in re.split(r'[;,]', str(keywords)) if k.strip()]
    found = [k for k in kws if all(tok in words for tok in tokenize(k))]
    frac = len(found)/len(kws) if kws else 1.0
    return frac, found

def length_score(transcript: str, minw: float, maxw: float) -> float:
    n = len(tokenize(transcript))
    if minw<=n<=maxw:
        return 1.0
    # penalize linearly outside range
    if n < minw:
        return max(0.0, n/minw)
    else:
        if n <= 2*maxw:
            return max(0.0, (2*maxw - n)/maxw)
        return 0.0

def semantic_similarity_score(a: str, b: str) -> float:
    """
    Returns a similarity score in [0,1]
    Uses sentence-transformers if available, otherwise TF-IDF + cosine.
    """
    if st_model is not None:
        try:
            vecs = st_model.encode([a,b], convert_to_numpy=True)
            sim = float(np.dot(vecs[0], vecs[1]) / (np.linalg.norm(vecs[0]) * np.linalg.norm(vecs[1]) + 1e-8))
            return (sim + 1)/2 if sim < -1 or sim > 1 else sim  # usually between 0-1 already
        except Exception:
            pass

    # fallback TF-IDF
    vect = TfidfVectorizer().fit_transform([a,b])
    cs = cosine_similarity(vect[0], vect[1])[0][0]
    return float(cs)

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
        sem_sim = semantic_similarity_score(transcript, desc) if desc.strip() else 1.0

        # Combining three signals
        combined = 0.2*kw_frac + 0.4*sem_sim + 0.4*len_sc
        # scale to criterion max_score
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
        # feedback generation
        fb = []
        if found_kws:
            fb.append(f"Found keywords: {', '.join(found_kws)}.")
        else:
            if keywords.strip():
                fb.append("No rubric keywords detected.")
        if len_sc < 0.9:
            fb.append("Transcript length outside suggested range.")
        if sem_sim < 0.5:
            fb.append("Low semantic similarity to rubric description.")
        per['feedback'] = " ".join(fb)

        per_criteria.append(per)
        overall_RAW += (crit_score * weight)

    # normalize overall to 0-100
    max_raw = (rubric_df['max_score'] * rubric_df['weight']).sum()
    overall_score = (overall_RAW / max_raw) * 100 if max_raw>0 else 0.0

    return {
        "overall_score": float(overall_score),
        "per_criteria": per_criteria,
        "words": len(tokenize(transcript))
    }
