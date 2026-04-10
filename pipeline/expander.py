import re
from .utils import claude_call, parse_json_response

DOMAIN_SIGNALS = {
    "nlp":      ["language model","nlp","bert","gpt","transformer","text mining",
                 "natural language","llm","named entity","clinical notes","discharge"],
    "imaging":  ["radiology","mri","ct scan","x-ray","ultrasound","echocardiograph",
                 "mammograph","pathology","histology","fundus","retinal","imaging"],
    "genomics": ["genome","genomic","dna","rna","snp","variant","mutation","sequencing",
                 "biomarker","proteomics","transcriptom"],
    "signal":   ["ecg","eeg","emg","ppg","waveform","signal","physiolog","biosignal",
                 "arrhythmia","heart rate","blood pressure"],
    "clinical": ["patient","hospital","icu","diagnosis","prognosis","treatment","outcome",
                 "clinical","disease","mortality","readmission","sepsis","diabetes"],
    "drug":     ["drug","molecule","compound","pharmacol","toxicol","binding","docking"],
    "ai_general":["deep learning","neural network","machine learning","classification",
                  "detection","prediction","model","benchmark","dataset"],
}

SYNONYMS = {
    "llm":                ["large language model","GPT","language model","foundation model"],
    "large language model":["LLM","GPT","generative AI","foundation model"],
    "ecg":                ["electrocardiogram","electrocardiography","12-lead ECG"],
    "mri":                ["magnetic resonance imaging","MRI scan","fMRI"],
    "ct":                 ["computed tomography","CT scan"],
    "ehr":                ["electronic health record","EMR","electronic medical record"],
    "icu":                ["intensive care unit","critical care"],
    "nlp":                ["natural language processing","text mining","clinical NLP"],
    "cnn":                ["convolutional neural network","ResNet","VGG"],
    "transformer":        ["attention mechanism","BERT","GPT","self-attention","ViT"],
    "diabetes":           ["type 2 diabetes","T2DM","insulin resistance"],
    "sepsis":             ["septic shock","bloodstream infection","bacteremia"],
    "cancer":             ["malignancy","oncology","tumour","carcinoma","neoplasm"],
    "deep learning":      ["neural network","CNN","representation learning"],
    "federated learning": ["distributed learning","privacy-preserving ML"],
    "decision support":   ["clinical decision support","CDSS"],
    "prediction":         ["prognosis","risk stratification","outcome prediction"],
}

MESH_MAP = {
    "nlp":          ["Natural Language Processing","Medical Informatics"],
    "imaging":      ["Diagnostic Imaging","Image Interpretation Computer-Assisted"],
    "ecg":          ["Electrocardiography","Arrhythmias Cardiac"],
    "deep learning":["Deep Learning","Neural Networks Computer"],
    "ehr":          ["Electronic Health Records","Medical Records Systems Computerized"],
    "sepsis":       ["Sepsis","Systemic Inflammatory Response Syndrome"],
    "diabetes":     ["Diabetes Mellitus Type 2","Blood Glucose"],
    "cancer":       ["Neoplasms","Oncology"],
    "federated":    ["Federated Learning","Privacy-Preserving Computation"],
    "drug":         ["Drug Discovery","Pharmacology","Molecular Docking"],
    "genomics":     ["Genomics","Genetic Variation","Sequence Analysis"],
    "signal":       ["Biosensing Techniques","Physiological Monitoring"],
}

def _detect_domain(topic):
    tl = topic.lower()
    for domain, signals in DOMAIN_SIGNALS.items():
        if any(s in tl for s in signals):
            return domain
    return "clinical"

def _find_synonyms(topic):
    tl = topic.lower()
    found = []
    for key, syns in SYNONYMS.items():
        if key in tl:
            found.extend(syns[:2])
    return list(dict.fromkeys(found))[:6]

def _find_mesh(topic):
    tl = topic.lower()
    terms = []
    for key, mesh in MESH_MAP.items():
        if key in tl:
            terms.extend(mesh)
    return list(dict.fromkeys(terms))[:4]

def _core_words(topic, n=3):
    stop = {"the","a","an","of","in","for","and","or","with","using","based","on",
            "to","from","by","at","is","are","was","were","how","what","why"}
    words = [w for w in topic.lower().split() if w not in stop]
    return " ".join(words[:n])

def _rule_based_expand(topic):
    domain   = _detect_domain(topic)
    synonyms = _find_synonyms(topic)
    mesh     = _find_mesh(topic)
    core     = _core_words(topic, 3)
    ai_mod   = "large language model" if domain == "nlp" else "deep learning"

    queries = [
        {"angle": "core",       "query": topic,
         "rationale": "Exact topic as entered"},
        {"angle": "method",     "query": f"{core} machine learning classification",
         "rationale": "ML methodology focus"},
        {"angle": "systematic", "query": f"{topic} systematic review meta-analysis",
         "rationale": "Highest evidence sources"},
        {"angle": "AI variant", "query": f"{core} {ai_mod}",
         "rationale": "Recent AI framing"},
        {"angle": "clinical",   "query": f"{core} clinical outcome prediction",
         "rationale": "Clinical application"},
        {"angle": "benchmark",  "query": f"{core} benchmark dataset evaluation",
         "rationale": "Comparative studies"},
    ]
    if synonyms:
        queries.append({"angle": "synonym", "query": synonyms[0] + " " + core,
                        "rationale": f"Synonym: {synonyms[0]}"})
    if mesh:
        queries.append({"angle": "MeSH", "query": mesh[0],
                        "rationale": "MeSH controlled vocabulary"})

    return {
        "original_topic":   topic,
        "expanded_queries": queries,
        "mesh_terms":       mesh,
        "synonyms":         synonyms,
        "domain_detected":  domain,
        "method":           "rule-based",
    }

def expand_query(topic, api_key=""):
    if api_key:
        prompt = f"""Topic: "{topic}"
Return JSON:
{{"original_topic":"{topic}","expanded_queries":[{{"query":"...","angle":"...","rationale":"..."}}],"mesh_terms":["..."],"synonyms":["..."],"domain_detected":"..."}}
Generate 6-8 queries: core, method, systematic review, AI variant, clinical, benchmark, MeSH."""
        raw = claude_call(prompt=prompt, api_key=api_key, max_tokens=1024)
        if raw:
            parsed = parse_json_response(raw)
            if parsed and "expanded_queries" in parsed:
                parsed["method"] = "claude"
                return parsed
    return _rule_based_expand(topic)