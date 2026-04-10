from datetime import datetime
from config import PRESTIGE_VENUES
from .utils import log

EVIDENCE_WEIGHT = {"1a":30,"1b":25,"2a":18,"2b":15,"3":10,"4":5,"5":2}

def score_paper(paper):
    score = 0
    bd = {}

    try:
        age = datetime.now().year - int(str(paper.get("year") or 0))
    except Exception:
        age = 10
    rec = max(0, 20 - age*2)
    score += rec
    bd["Recency"] = rec

    cit = min(25, int((paper.get("citations") or 0) / 5))
    score += cit
    bd["Citations"] = cit

    ev_level = (paper.get("classification") or {}).get("evidence_level", "5")
    ev = int(EVIDENCE_WEIGHT.get(ev_level, 2) * 15 / 30)
    score += ev
    bd["Evidence Level"] = ev

    ft = 15 if paper.get("full_text") else 0
    score += ft
    bd["Full Text"] = ft

    ab = min(10, len(paper.get("abstract") or "") // 50)
    score += ab
    bd["Abstract"] = ab

    oa = 8 if paper.get("open_access") else 0
    score += oa
    bd["Open Access"] = oa

    venue = (paper.get("venue") or "").lower()
    pres = 7 if any(k in venue for k in PRESTIGE_VENUES) else 3
    score += pres
    bd["Venue"] = pres

    grade = "A" if score >= 75 else "B" if score >= 55 else "C" if score >= 35 else "D"
    return {"score": score, "grade": grade, "breakdown": bd}

def score_all(papers):
    for paper in papers:
        paper["quality"] = score_paper(paper)
    return papers

def semantic_rank(topic, papers, top_k=30):
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        docs = [
            f"{p.get('title','')} {p.get('abstract','')} "
            f"{' '.join((p.get('classification') or {}).get('topics', []))}"
            for p in papers
        ]
        corpus = [topic] + docs
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1,2), max_features=8000)
        mat = vec.fit_transform(corpus)
        scores = cosine_similarity(mat[0:1], mat[1:])[0]
        for i, paper in enumerate(papers):
            paper["semantic_score"] = float(scores[i])
        ranked = sorted(papers, key=lambda p: (
            p["semantic_score"] * 0.5 +
            p.get("quality", {}).get("score", 0) / 100 * 0.5
        ), reverse=True)
        return ranked[:top_k]
    except ImportError:
        log.warning("sklearn not available - using quality-score ranking")
        for p in papers:
            p["semantic_score"] = 0.0
        return sorted(papers,
                      key=lambda p: p.get("quality", {}).get("score", 0),
                      reverse=True)[:top_k]
