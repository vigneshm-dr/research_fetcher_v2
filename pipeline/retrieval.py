import re, time
import xml.etree.ElementTree as ET
from .utils import safe_get, xml_text, log

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
JATS   = "http://jats.nlm.nih.gov"
XLINK  = "http://www.w3.org/1999/xlink"
ATOM   = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

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
        "source": "pubmed", "pmid": pmid, "pmc_id": pmc_id, "doi": doi,
        "title": title or "Untitled", "authors": authors, "year": year,
        "abstract": abstract, "venue": journal, "open_access": bool(pmc_id),
        "full_text": full_text, "images": images, "citations": 0,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "pdf_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/" if pmc_id else "",
        "pub_types": [],
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
        images.append({"url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/bin/{href}.jpg",
                       "label": label, "caption": caption, "filename": f"{href}.jpg"})
    return (sections or None), images

def search_arxiv(query, n):
    r = safe_get("http://export.arxiv.org/api/query",
                 params={"search_query":f"all:{query}","start":0,"max_results":n,"sortBy":"relevance"})
    if not r:
        return []
    try:
        root = ET.fromstring(r.content)
    except Exception:
        return []
    papers = []
    for entry in root.findall("atom:entry", ATOM):
        raw_id   = entry.findtext("atom:id","",ATOM)
        arxiv_id = raw_id.split("/abs/")[-1].split("v")[0]
        title    = entry.findtext("atom:title","",ATOM).strip().replace("\n"," ")
        abstract = entry.findtext("atom:summary","",ATOM).strip()
        year     = entry.findtext("atom:published","",ATOM)[:4]
        authors  = [a.findtext("atom:name","",ATOM) for a in entry.findall("atom:author",ATOM)]
        cats     = [c.get("term","") for c in entry.findall("arxiv:primary_category",ATOM)]
        venue    = cats[0] if cats else "arXiv"
        doi_el   = entry.find("arxiv:doi",ATOM)
        doi      = doi_el.text.strip() if doi_el is not None else ""
        full_text, images = _arxiv_fulltext(arxiv_id)
        papers.append({
            "source":"arxiv","arxiv_id":arxiv_id,"doi":doi,
            "title":title or "Untitled","authors":authors,"year":year,
            "abstract":abstract,"venue":venue,"open_access":True,
            "full_text":full_text,"images":images,"citations":0,
            "url":f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url":f"https://arxiv.org/pdf/{arxiv_id}","pub_types":[],
        })
        time.sleep(0.2)
    return papers

def _arxiv_fulltext(arxiv_id):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None, []
    r = safe_get(f"https://ar5iv.org/html/{arxiv_id}", timeout=25)
    if not r or r.status_code != 200:
        return None, []
    soup = BeautifulSoup(r.text, "html.parser")
    sections = []
    for sec in soup.find_all("section", class_=re.compile(r"ltx_(section|subsection)")):
        h    = sec.find(re.compile(r"^h[1-6]$"))
        ttl  = h.get_text(strip=True) if h else ""
        body = [p.get_text(" ",strip=True) for p in sec.find_all("p") if len(p.get_text(strip=True))>60]
        if body:
            sections.append({"title":ttl,"content":"\n\n".join(body)})
    images = []
    for fig in soup.find_all("figure"):
        img = fig.find("img")
        cap = fig.find("figcaption")
        if not img:
            continue
        src = img.get("src","")
        if not src:
            continue
        if not src.startswith("http"):
            src = f"https://ar5iv.org{src}"
        fn = re.sub(r"[^a-zA-Z0-9._-]","_",src.split("/")[-1])
        images.append({"url":src,"label":"","caption":(cap.get_text(" ",strip=True) if cap else "")[:300],"filename":fn})
    return (sections or None), images

SS_FIELDS = ("title,abstract,year,authors,citationCount,"
             "isOpenAccess,venue,externalIds,openAccessPdf,publicationTypes,journal")

def search_semantic_scholar(query, n, api_key=""):
    headers = {"x-api-key": api_key} if api_key else {}
    r = safe_get("https://api.semanticscholar.org/graph/v1/paper/search",
                 params={"query":query,"limit":n,"fields":SS_FIELDS}, headers=headers)
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
            "source":"semantic_scholar","doi":doi,"arxiv_id":arxiv,"pmid":pmid,
            "title":p.get("title") or "Untitled",
            "authors":[a.get("name","") for a in (p.get("authors") or [])],
            "year":p.get("year") or "","abstract":p.get("abstract") or "",
            "venue":journal,"open_access":p.get("isOpenAccess",False),
            "full_text":None,"images":[],"citations":p.get("citationCount") or 0,
            "pub_types":p.get("publicationTypes") or [],
            "url":f"https://doi.org/{doi}" if doi else "","pdf_url":pdf_url,
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
        for paper in search_arxiv(q, n_per):
            paper["query_angle"] = angle
            all_papers.append(paper)
        for paper in search_semantic_scholar(q, n_per, s2_key):
            paper["query_angle"] = angle
            all_papers.append(paper)
        time.sleep(0.5)
    return all_papers