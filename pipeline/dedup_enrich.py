import re
from .utils import safe_get, log

def _doi_key(paper):
    doi = (paper.get("doi") or "").strip().lower()
    return doi if doi else None

def _title_key(paper):
    t = (paper.get("title") or "").lower()
    return re.sub(r"[^a-z0-9]","",t)[:80]

def deduplicate(papers):
    def richness(p):
        return (10*bool(p.get("full_text"))
                + len(p.get("abstract") or "")/100
                + (p.get("citations") or 0)/100)

    doi_seen, title_seen = {}, {}
    for paper in papers:
        doi_k   = _doi_key(paper)
        title_k = _title_key(paper)
        if doi_k:
            if doi_k not in doi_seen or richness(paper) > richness(doi_seen[doi_k]):
                doi_seen[doi_k] = paper
        else:
            if title_k not in title_seen or richness(paper) > richness(title_seen[title_k]):
                title_seen[title_k] = paper

    seen_titles = {_title_key(p) for p in doi_seen.values()}
    deduped = list(doi_seen.values())
    for tk, p in title_seen.items():
        if tk not in seen_titles:
            deduped.append(p)
    log.info(f"Dedup: {len(papers)} → {len(deduped)} papers")
    return deduped

SS_FIELDS = "citationCount,isOpenAccess,venue,journal,externalIds,openAccessPdf,publicationTypes"

def enrich(papers, s2_key=""):
    headers = {"x-api-key": s2_key} if s2_key else {}
    enriched = []
    for paper in papers:
        if (paper.get("citations") or 0) > 0:
            enriched.append(paper)
            continue
        paper_id = None
        if paper.get("doi"):
            paper_id = f"DOI:{paper['doi']}"
        elif paper.get("arxiv_id"):
            paper_id = f"ARXIV:{paper['arxiv_id']}"
        elif paper.get("pmid"):
            paper_id = f"PMID:{paper['pmid']}"
        if paper_id:
            r = safe_get(f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}",
                         params={"fields": SS_FIELDS}, headers=headers, timeout=10)
            if r:
                data = r.json()
                paper["citations"]   = data.get("citationCount") or paper.get("citations",0)
                paper["open_access"] = data.get("isOpenAccess") or paper.get("open_access",False)
                paper["pub_types"]   = data.get("publicationTypes") or paper.get("pub_types",[])
                if not paper.get("pdf_url"):
                    paper["pdf_url"] = (data.get("openAccessPdf") or {}).get("url","")
                if not paper.get("venue") and data.get("journal"):
                    paper["venue"] = (data["journal"] or {}).get("name","")
        enriched.append(paper)
    return enriched