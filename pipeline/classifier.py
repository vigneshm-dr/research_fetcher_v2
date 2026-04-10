import re
from .utils import claude_call, parse_json_response, truncate, log

_STUDY_RULES = [
    (["cochrane","systematic review and meta","meta-analysis of randomised"],
     "Meta-Analysis","1a"),
    (["systematic review"],                                      "Systematic Review","1a"),
    (["randomised controlled trial","randomized controlled trial",
      "rct","double-blind","placebo-controlled"],                "Randomised Controlled Trial","1b"),
    (["prospective cohort","retrospective cohort","cohort study","longitudinal study"],
     "Cohort Study","2b"),
    (["case-control","case control study"],                      "Case-Control Study","3"),
    (["cross-sectional","prevalence study","survey study"],      "Cross-Sectional Study","3"),
    (["case series","case report","case presentation"],          "Case Series/Report","4"),
    (["narrative review","literature review","scoping review"],  "Narrative Review","5"),
    (["editorial","commentary","letter to the editor"],          "Editorial/Commentary","5"),
    (["we propose","we present","we introduce","novel framework","novel architecture",
      "benchmark","dataset","we evaluate","our model","deep learning",
      "neural network","transformer","algorithm"],               "Technical/Methods Paper","5"),
]

_PUBTYPE_MAP = {
    "systematicreview":          ("Systematic Review","1a"),
    "meta-analysis":             ("Meta-Analysis","1a"),
    "randomizedcontrolledtrial": ("Randomised Controlled Trial","1b"),
    "clinicaltrial":             ("Randomised Controlled Trial","1b"),
    "observationalstudy":        ("Cohort Study","2b"),
    "casereport":                ("Case Series/Report","4"),
    "review":                    ("Narrative Review","5"),
    "editorial":                 ("Editorial/Commentary","5"),
    "preprint":                  ("Preprint","5"),
}

_DOMAIN_RULES = [
    (["large language model","llm","gpt","bert","chatgpt","clinical nlp",
      "natural language processing","text mining","named entity",
      "clinical notes","discharge summary"],                     "NLP"),
    (["radiology","mri","magnetic resonance","ct scan","computed tomography",
      "x-ray","chest radiograph","ultrasound","echocardiograph",
      "mammograph","histology","pathology slide","digital pathology"],  "Medical Imaging"),
    (["ecg","electrocardiogram","eeg","electroencephalogram","ppg",
      "biosignal","physiological signal","waveform","arrhythmia"],  "Physiology & Signals"),
    (["genome","genomic","dna","rna","snp","variant","mutation",
      "sequencing","transcriptom","proteom","biomarker"],         "Genomics"),
    (["drug discovery","molecular docking","compound","pharmacol",
      "adverse drug","drug interaction"],                         "Drug Discovery"),
    (["epidemiol","prevalence","incidence","population-based",
      "public health","mortality rate"],                          "Epidemiology"),
    (["federated learning","privacy-preserving","differential privacy"],
     "Federated / Privacy ML"),
]

_RELEVANCE_RULES = [
    (["patient","clinical","hospital","diagnosis","prognosis",
      "treatment","outcome","mortality","survival","readmission",
      "icu","clinical trial","disease"],                          "High"),
    (["model","algorithm","system","framework","application",
      "performance","accuracy","auc","f1"],                       "Medium"),
    (["theoretical","proof","mathematical","formal analysis",
      "synthetic data"],                                          "Low"),
]

_FINDING_SIGNALS = [
    "we found","we show","we demonstrate","results show","our model achieved",
    "accuracy of","auc of","sensitivity of","outperform","significantly",
    "we conclude","in conclusion","our approach",
]

def _extract_key_finding(abstract):
    if not abstract:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", abstract.strip())
    for sent in reversed(sentences):
        if any(sig in sent.lower() for sig in _FINDING_SIGNALS):
            words = sent.split()
            return " ".join(words[:30]) + ("…" if len(words)>30 else "")
    return " ".join(sentences[-1].split()[:30]) if sentences else ""

def _extract_topics(title, abstract, domain):
    text  = f"{title} {abstract}"
    caps  = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", text)
    tech  = [t for t in re.findall(r"\b\w+(?:-\w+)+\b", text.lower()) if len(t)>4]
    terms = list(dict.fromkeys(caps[:4]+tech[:4]))
    terms.insert(0, domain)
    return terms[:6]

def _heuristic_classify(paper):
    title    = paper.get("title") or ""
    abstract = paper.get("abstract") or ""
    text     = (title+" "+abstract).lower()
    pub_types = [re.sub(r"\s+","",t).lower() for t in (paper.get("pub_types") or [])]

    study_type, level = "Other", "5"
    for pt in pub_types:
        if pt in _PUBTYPE_MAP:
            study_type, level = _PUBTYPE_MAP[pt]
            break
    if study_type == "Other":
        for signals, st, lv in _STUDY_RULES:
            if any(s in text for s in signals):
                study_type, level = st, lv
                break

    domain = "Clinical Medicine"
    for signals, dom in _DOMAIN_RULES:
        if any(s in text for s in signals):
            domain = dom
            break

    clinical_relevance = "Non-clinical"
    for signals, rel in _RELEVANCE_RULES:
        if any(s in text for s in signals):
            clinical_relevance = rel
            break

    return {
        "study_type":         study_type,
        "evidence_level":     level,
        "topics":             _extract_topics(title, abstract, domain),
        "clinical_relevance": clinical_relevance,
        "domain":             domain,
        "key_finding":        _extract_key_finding(abstract),
        "classified_by":      "rule-based",
    }

def classify_paper(paper, api_key=""):
    abstract = truncate(paper.get("abstract") or "", 1500)
    if api_key and abstract:
        prompt = f"""Classify this paper. Return JSON only.
Title: {paper.get('title','')}
Abstract: {abstract}
Schema: {{"study_type":"...","evidence_level":"1a|1b|2a|2b|3|4|5","topics":[],"clinical_relevance":"High|Medium|Low|Non-clinical","domain":"...","key_finding":"..."}}"""
        raw = claude_call(prompt=prompt, api_key=api_key, max_tokens=512)
        if raw:
            parsed = parse_json_response(raw)
            if parsed and "study_type" in parsed:
                parsed["classified_by"] = "claude"
                return parsed
    return _heuristic_classify(paper)

def classify_all(papers, api_key=""):
    for paper in papers:
        paper["classification"] = classify_paper(paper, api_key)
    return papers