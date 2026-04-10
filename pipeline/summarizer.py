import re
from .utils import claude_call, parse_json_response, truncate, log

_SECTION_PATTERNS = {
    "objective":   re.compile(r"(background|purpose|aim|objective|introduction)[s]?\b",re.I),
    "methods":     re.compile(r"(method|material|patient|design|setting|data)[s]?\b",re.I),
    "results":     re.compile(r"(result|finding|outcome|performance|accuracy|auc)[s]?\b",re.I),
    "conclusions": re.compile(r"(conclusion|discussion|implication|limitation|summary)[s]?\b",re.I),
}

def _split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+",text.strip()) if len(s.strip())>20]

def _extract_from_abstract(abstract):
    parts = {}
    for field, pat in _SECTION_PATTERNS.items():
        m = re.search(
            rf"(?:^|\n)\s*{pat.pattern}[:\s]+(.+?)(?=\n\s*(?:{'|'.join(_SECTION_PATTERNS.keys())})\b|\Z)",
            abstract, re.I|re.S)
        if m:
            parts[field] = m.group(1).strip()[:300]
    if parts:
        return parts
    sentences = _split_sentences(abstract)
    n = len(sentences)
    return {
        "objective":   sentences[0][:250] if n>=1 else "",
        "methods":     sentences[n//4][:250] if n>=4 else "",
        "results":     sentences[n//2][:250] if n>=2 else "",
        "conclusions": " ".join(sentences[max(0,n-2):])[:300] if n>=2 else abstract[:300],
    }

def _extract_from_fulltext(full_text):
    out = {}
    for sec in (full_text or []):
        title = (sec.get("title") or "").lower()
        body  = sec.get("content","")[:300]
        for field, pat in _SECTION_PATTERNS.items():
            if field not in out and pat.search(title):
                out[field] = body
    return out

def _tldr(abstract):
    sentences = _split_sentences(abstract)
    if not sentences:
        return ""
    tail = sentences[-2:] if len(sentences)>=2 else sentences
    return " ".join(tail)[:280]

def _key_terms(paper):
    topics = (paper.get("classification") or {}).get("topics",[])
    title_words = [w for w in re.findall(r"\b[A-Z][a-zA-Z]{3,}\b",paper.get("title",""))
                   if w.lower() not in {"this","that","with","from","their","which"}]
    return list(dict.fromkeys(topics+title_words))[:8]

def _extractive_summarise(paper):
    abstract  = paper.get("abstract") or ""
    full_text = paper.get("full_text") or []
    cls       = paper.get("classification") or {}
    ft_parts  = _extract_from_fulltext(full_text) if full_text else {}
    ab_parts  = _extract_from_abstract(abstract)
    def pick(field): return ft_parts.get(field) or ab_parts.get(field,"")
    return {
        "tldr":                  _tldr(abstract),
        "objective":             pick("objective"),
        "methods":               pick("methods"),
        "results":               pick("results"),
        "conclusions":           pick("conclusions"),
        "limitations":           "",
        "clinical_implications": (f"This {cls.get('study_type','study').lower()} contributes to "
                                  f"{cls.get('domain','research').lower()}. "
                                  f"Clinical relevance: {cls.get('clinical_relevance','?')}."),
        "key_terms":             _key_terms(paper),
        "summarised_by":         "extractive",
    }

def summarise_paper(paper, api_key=""):
    cls      = paper.get("classification") or {}
    abstract = truncate(paper.get("abstract") or "", 2000)
    if api_key and abstract:
        ft = paper.get("full_text") or []
        excerpt = "\n".join(s.get("content","")[:300] for s in ft[:3])
        fulltext_block = f"Full Text Excerpt:\n{truncate(excerpt,1500)}" if excerpt else ""
        prompt = f"""Summarise for an LLM wiki. Return JSON only.
Title: {paper.get('title','')}
Study Type: {cls.get('study_type','Unknown')}
Abstract: {abstract}
{fulltext_block}
Schema: {{"tldr":"...","objective":"...","methods":"...","results":"...","conclusions":"...","limitations":"...","clinical_implications":"...","key_terms":[]}}"""
        raw = claude_call(prompt=prompt, api_key=api_key, max_tokens=1024)
        if raw:
            parsed = parse_json_response(raw)
            if parsed and "tldr" in parsed:
                parsed["summarised_by"] = "claude"
                return parsed
    return _extractive_summarise(paper)

def summarise_all(papers, api_key=""):
    for paper in papers:
        paper["summary"] = summarise_paper(paper, api_key)
    return papers