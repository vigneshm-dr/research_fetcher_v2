import json, re, requests
from datetime import datetime
from pathlib import Path
from .utils import slugify, log

def _download_images(images, slug, img_dir):
    saved = []
    for img in images:
        try:
            filename = f"{slug}__{img.get('filename','fig.jpg')}"
            dest = img_dir / filename
            r = requests.get(img["url"], stream=True, timeout=15,
                             headers={"User-Agent":"ResearchFetcher/2.0"})
            if r and r.status_code == 200:
                with open(dest,"wb") as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
                saved.append({**img,"saved_filename":filename})
        except Exception as e:
            log.warning(f"Image download failed: {e}")
    return saved

def _grade_emoji(grade):
    return {"A":"🟢","B":"🔵","C":"🟡","D":"🔴"}.get(grade,"⚪")

def _build_markdown(paper, saved_images, img_dir):
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")
    q    = paper.get("quality") or {}
    cls  = paper.get("classification") or {}
    summ = paper.get("summary") or {}
    grade = q.get("grade","?")
    lines = [
        f"# {paper['title']}",
        f"> {_grade_emoji(grade)} **{grade} ({q.get('score',0)}/100)** · {cls.get('study_type','?')} · Level {cls.get('evidence_level','?')} · {cls.get('domain','?')}",
        "","## Metadata","",
        "| Field | Value |","|-------|-------|",
        f"| Source | {paper.get('source','').replace('_',' ').title()} |",
        f"| Year | {paper.get('year','N/A')} |",
        f"| Authors | {', '.join((paper.get('authors') or [])[:6])} |",
        f"| Venue | {paper.get('venue','N/A')} |",
        f"| Citations | {paper.get('citations','N/A')} |",
        f"| Open Access | {'✅' if paper.get('open_access') else '❌'} |",
        f"| DOI | {paper.get('doi','N/A')} |",
        f"| URL | [{paper.get('url','')}]({paper.get('url','')}) |",
        f"| Topics | {', '.join(cls.get('topics',[]))} |",
        f"| Key Finding | {cls.get('key_finding','')} |",
        "","## Quality Breakdown","","| Criterion | Score |","|-----------|------:|",
    ]
    for k,v in (q.get("breakdown") or {}).items():
        lines.append(f"| {k} | {v} |")
    if summ.get("tldr"):
        lines += ["","## Summary",f"**TL;DR:** {summ['tldr']}",""]
        for field in ["objective","methods","results","conclusions","limitations","clinical_implications"]:
            if summ.get(field):
                lines.append(f"**{field.replace('_',' ').title()}:** {summ[field]}")
        lines.append(f"\n**Key Terms:** {', '.join(summ.get('key_terms',[]))}")
    if paper.get("abstract"):
        lines += ["","---","## Abstract","",paper["abstract"]]
    if paper.get("full_text"):
        lines += ["","---","## Full Text",""]
        for sec in paper["full_text"]:
            if sec.get("title"): lines += [f"### {sec['title']}",""]
            lines += [sec["content"],""]
    if saved_images:
        lines += ["","---","## Figures",""]
        for img in saved_images:
            fn  = img.get("saved_filename",img.get("filename",""))
            alt = img.get("label") or fn
            lines += [f"![{alt}]({img_dir/fn})",f"*{img.get('caption','')}*",""]
    lines += ["---",f"*Fetched by ResearchFetcher v2 · {now}*"]
    return "\n".join(lines)

def _build_json_record(paper, saved_images, md_path):
    return {
        "title":paper.get("title",""),"source":paper.get("source",""),
        "year":paper.get("year",""),"authors":paper.get("authors",[]),
        "venue":paper.get("venue",""),"doi":paper.get("doi",""),
        "url":paper.get("url",""),"pdf_url":paper.get("pdf_url",""),
        "citations":paper.get("citations",0),"open_access":paper.get("open_access",False),
        "abstract":paper.get("abstract",""),"quality":paper.get("quality",{}),
        "classification":paper.get("classification",{}),"summary":paper.get("summary",{}),
        "semantic_score":paper.get("semantic_score",0.0),
        "has_full_text":bool(paper.get("full_text")),
        "figure_count":len(saved_images),
        "saved_images":[i.get("saved_filename","") for i in saved_images],
        "markdown_file":str(md_path),"fetched_at":datetime.now().isoformat(),
    }

def write_paper(paper, md_dir, img_dir, json_dir):
    try:
        slug       = slugify(paper.get("title",""))
        saved_imgs = _download_images(paper.get("images") or [], slug, img_dir)
        md_path    = md_dir / f"{slug}.md"
        md_path.write_text(_build_markdown(paper, saved_imgs, img_dir), encoding="utf-8")
        record     = _build_json_record(paper, saved_imgs, md_path)
        (json_dir/f"{slug}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False))
        return record
    except Exception as e:
        log.warning(f"Failed to write '{paper.get('title','')}': {e}")
        return None

def write_all(papers, md_dir, img_dir, json_dir, min_grade="B"):
    grade_order = ["A","B","C","D"]
    min_idx     = grade_order.index(min_grade)
    for d in [md_dir, img_dir, json_dir]: d.mkdir(parents=True, exist_ok=True)
    records = []
    for paper in papers:
        grade = (paper.get("quality") or {}).get("grade","D")
        if grade_order.index(grade) > min_idx:
            continue
        record = write_paper(paper, md_dir, img_dir, json_dir)
        if record: records.append(record)
    index_path = json_dir/"_corpus_index.json"
    existing   = []
    if index_path.exists():
        try: existing = json.loads(index_path.read_text())
        except Exception: pass
    seen   = {r["title"] for r in records}
    merged = [r for r in existing if r.get("title") not in seen] + records
    index_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    return records