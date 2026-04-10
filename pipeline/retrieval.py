import re, time
import xml.etree.ElementTree as ET
from .utils import safe_get, xml_text, log

EUTILS      = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
JATS        = "http://jats.nlm.nih.gov"
XLINK       = "http://www.w3.org/1999/xlink"
MEDRXIV_API = "https://api.medrxiv.org/details/medrxiv"


def _ncbi_params(extra, api_key):
    p = dict(extra)
    if api_key:
        p["api_key"] = api_key
    return p

def search_pubmed(query, n, api_key=""):
    r = safe_get(f"{EUTILS}/esearch.fcgi",
                 params=_ncbi_params({"db":"pubmed","term":query,
                                      "retmax":n,"retmode":"json","sort":"relevance"}, api_key))
    if not r:
        return []
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    out = []
    for pmid in ids:
        p = _pubmed_detail(pmid, api_key)
        if p:
            out.append(p)
        time.sleep(0.34 if api_key else 0.7)
    return out

def _pubmed_detail(pmid, api_key):
    r = safe_get(f"{EUTILS}/efetch.fcgi",
                 params=_ncbi_params({"db":"pubmed","id":pmid,"retmode":"xml"}, api_key))
    if not r:
        return None
    try:
        root = ET.fromstring(r.content)
    except Exception:
        return None
    art = root.find(".//MedlineCitation")
    if art is None:
        return None
    title    = xml_text(art.find(".//ArticleTitle"))
    abstract = " ".join(xml_text(a) for a in art.findall(".//AbstractText"))
    year_el  = art.find(".//PubDate/Year") or art.find(".//PubDate/MedlineDate")
    year     = (year_el.text or "")[:4] if year_el is not None else ""
    journal  = xml_text(art.find(".//Journal/Title"))
    doi_el   = art.find(".//ArticleId[@IdType='doi']") or root.find(".//ArticleId[@IdType='doi']")
    doi      = doi_el.text if doi_el is not None else ""
    authors  = [f"{xml_text(a.find('LastName'))} {xml_text(a.find('ForeName'))}".strip()
                for a in art.findall(".//Author") if a.find("LastName") is not None]
    pmc_id   = _get_pmc_link(pmid, api_key)
    full_text, images = _pmc_fulltext(pmc_id) if pmc_id else (None, [])
    return {
        "source":      "pubmed",
        "pmid":        pmid,
        "pmc_id":      pmc_id,
        "doi":         doi,
        "arxiv_id":    "",
        "title":       title or "Untitled",
        "authors":     authors,
        "year":        year,
        "abstract":    abstract,
        "venue":       journal,
        "open_access": bool(pmc_id),
        "full_text":   full_text,
        "images":      images,
        "citations":   0,
        "pub_types":   [],
        "url":         f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "pdf_url":     f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/" if pmc_id else "",
    }

def _get_pmc_link(pmid, api_key):
    r = safe_get(f"{EUTILS}/elink.fcgi",
                 params=_ncbi_params({"dbfrom":"pubmed","db":"pmc","id":pmid,"retmode":"json"}, api_key))
    if not r:
        return None
    try:
        for ls in r.json().get("linksets",[{}])[0].get("linksetdbs",[]):
            if ls.get("dbto") == "pmc":
                ids = ls.get("links",[])
                return str(ids[0]) if ids else None
    except Exception:
        return None

def _pmc_fulltext(pmc_id):
    r = safe_get(f"{EUTILS}/efetch.fcgi",
                 params={"db":"pmc","id":pmc_id,"rettype":"full","retmode":"xml"})
    if not r:
        return None, []
    try:
        root = ET.fromstring(r.content)
    except Exception:
        return None, []
    sections = []
    for sec in root.findall(f".//{{{JATS}}}sec"):
        ttl  = xml_text(sec.find(f"{{{JATS}}}title"))
        body = [xml_text(p) for p in sec.findall(f"{{{JATS}}}p") if len(xml_text(p)) > 40]
        if body:
            sections.append({"title": ttl, "content": "\n\n".join(body)})
    images = []
    for fig in root.findall(f".//{{{JATS}}}fig"):
        g = fig.find(f".//{{{JATS}}}graphic")
        if g is None:
            continue
        href = g.get(f"{{{XLINK}}}href","")
        if not href:
            continue
        label   = xml_text(fig.find(f"{{{JATS}}}label"))
        cap_p   = fig.find(f".//{{{JATS}}}p")
        caption = xml_text(cap_p) if cap_p is not None else ""
        images.append({
            "url":      f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/bin/{href}.jpg",
            "label":    label,
            "caption":  caption,
            "filename": f"{href}.jpg",
        })
    return (sections or None), images


def search_medrxiv(query, n, max_pages=5):
    from datetime import datetime, timedelta
    end_date   = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=365*3)).strftime("%Y-%m-%d")
    keywords   = [w.lower() for w in re.split(r'\s+', query) if len(w) > 3]
    candidates = []
    cursor     = 0
    for _ in range(max_pages):
        r = safe_get(f"{MEDRXIV_API}/{start_date}/{end_date}/{cursor}/json")
        if not r:
            break
        try:
            data = r.json()
        except Exception:
            break
        collection = data.get("collection", [])
        if not collection:
            break
        for item in collection:
            title    = item.get("title", "") or ""
            abstract = item.get("abstract", "") or ""
            text     = (title + " " + abstract).lower()
            score    = sum(1 for kw in keywords if kw in text)
            if score > 0:
                candidates.append((score, item))
        cursor += 100
        time.sleep(0.3)
    candidates.sort(key=lambda x: x[0], reverse=True)
    papers = []
    for _, item in candidates[:n]:
        doi      = item.get("doi", "") or ""
        title    = item.get("title", "") or "Untitled"
        abstract = item.get("abstract", "") or ""
        date     = item.get("date", "") or ""
        year     = date[:4] if date else ""
        authors  = _parse_medrxiv_authors(item.get("authors", ""))
        category = item.get("category", "") or "medRxiv"
        version  = item.get("version", "1")
        papers.append({
            "source":      "medrxiv",
            "doi":         doi,
            "arxiv_id":    "",
            "pmid":        "",
            "title":       title,
            "authors":     authors,
            "year":        year,
            "abstract":    abstract,
            "venue":       f"medRxiv ({category})",
            "open_access": True,
            "full_text":   None,
            "images":      [],
            "citations":   0,
            "pub_types":   ["Preprint"],
            "url":         f"https://www.medrxiv.org/content/{doi}v{version}" if doi else "",
            "pdf_url":     f"https://www.medrxiv.org/content/{doi}v{version}.full.pdf" if doi else "",
        })
    log.info(f"medRxiv: scanned {cursor} papers, matched {len(candidates)}, returning {len(papers)}")
    return papers

def _parse_medrxiv_authors(authors_str):
    if not authors_str:
        return []
    return [a.strip() for a in authors_str.split(";") if a.strip()][:10]


SS_FIELDS = ("title,abstract,year,authors,citationCount,"
             "isOpenAccess,venue,externalIds,openAccessPdf,publicationTypes,journal")

def search_semantic_scholar(query, n, api_key=""):
    headers = {"x-api-key": api_key} if api_key else {}
    r = safe_get("https://api.semanticscholar.org/graph/v1/paper/search",
                 params={"query":query,"limit":n,"fields":SS_FIELDS},
                 headers=headers)
    if not r:
        return []
    papers = []
    for p in r.json().get("data",[]):
        ext     = p.get("externalIds") or {}
        doi     = ext.get("DOI","")
        arxiv   = ext.get("ArXiv","")
        pmid    = ext.get("PubMed","")
        pdf_url = (p.get("openAccessPdf") or {}).get("url","")
        journal = (p.get("journal") or {}).get("name","") or p.get("venue","")
        papers.append({
            "source":      "semantic_scholar",
            "doi":         doi,
            "arxiv_id":    arxiv,
            "pmid":        pmid,
            "title":       p.get("title") or "Untitled",
            "authors":     [a.get("name","") for a in (p.get("authors") or [])],
            "year":        p.get("year") or "",
            "abstract":    p.get("abstract") or "",
            "venue":       journal,
            "open_access": p.get("isOpenAccess", False),
            "full_text":   None,
            "images":      [],
            "citations":   p.get("citationCount") or 0,
            "pub_types":   p.get("publicationTypes") or [],
            "url":         f"https://doi.org/{doi}" if doi else "",
            "pdf_url":     pdf_url,
        })
    return papers


def retrieve_all(expanded_queries, n_per, ncbi_key="", s2_key=""):
    all_papers = []
    for item in expanded_queries:
        q     = item["query"]
        angle = item.get("angle","")
        log.info(f"  Fetching [{angle}]: {q}")
        for paper in search_pubmed(q, n_per, ncbi_key):
            paper["query_angle"] = angle
            all_papers.append(paper)
        for paper in search_medrxiv(q, n_per):
            paper["query_angle"] = angle
            all_papers.append(paper)
        for paper in search_semantic_scholar(q, n_per, s2_key):
            paper["query_angle"] = angle
            all_papers.append(paper)
        time.sleep(0.5)
    return all_papers
