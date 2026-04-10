from pathlib import Path
from typing import Callable
from .expander      import expand_query
from .retrieval     import retrieve_all
from .dedup_enrich  import deduplicate, enrich
from .classifier    import classify_all
from .scorer_ranker import score_all, semantic_rank
from .summarizer    import summarise_all
from .writer        import write_all
from .utils         import log

def run(topic, n_per_source=8, min_grade="B",
        md_dir=Path("~/llm_wiki/papers").expanduser(),
        img_dir=Path("~/llm_wiki/images").expanduser(),
        json_dir=Path("~/llm_wiki/json").expanduser(),
        anthropic_key="", ncbi_key="", s2_key="",
        top_k=30, emit: Callable[[str],None]=print) -> dict:

    results = {"topic":topic,"stages":{},"papers":[],"records":[]}

    emit("━━ Stage 1 · Query Expansion ━━━━━━━━━━━━━━━━━━━━━━━━━━")
    expansion = expand_query(topic, api_key=anthropic_key)
    queries   = expansion["expanded_queries"]
    emit(f"  Method: {expansion.get('method','rule-based')}  ·  Domain: {expansion.get('domain_detected','?')}")
    for q in queries:
        emit(f"  → [{q.get('angle','-')}] {q['query']}")
    results["stages"]["expansion"] = expansion

    emit("\n━━ Stage 2 · Multi-Source Retrieval ━━━━━━━━━━━━━━━━━━━")
    papers = retrieve_all(queries, n_per_source, ncbi_key, s2_key)
    emit(f"  ✓ Raw papers: {len(papers)}")
    results["stages"]["retrieval_count"] = len(papers)

    emit("\n━━ Stage 3 · Deduplication ━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    before = len(papers)
    papers = deduplicate(papers)
    emit(f"  ✓ {before} → {len(papers)} (removed {before-len(papers)} duplicates)")
    results["stages"]["after_dedup"] = len(papers)

    emit("\n━━ Stage 4 · Metadata Enrichment ━━━━━━━━━━━━━━━━━━━━━━")
    papers = enrich(papers, s2_key)
    has_cit = sum(1 for p in papers if (p.get("citations") or 0)>0)
    emit(f"  ✓ Citations filled for {has_cit}/{len(papers)} papers")

    emit("\n━━ Stage 5 · Classification ━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    papers = classify_all(papers, api_key=anthropic_key)
    by_type = {}
    for p in papers:
        st = (p.get("classification") or {}).get("study_type","Unknown")
        by_type[st] = by_type.get(st,0)+1
    emit(f"  Method: {'Claude API' if anthropic_key else 'Rule-based'}")
    for st, cnt in sorted(by_type.items(), key=lambda x:-x[1]):
        emit(f"    {cnt}×  {st}")

    emit("\n━━ Stage 6 · Quality Scoring ━━━━━━━━━━━━━━━━━━━━━━━━━━")
    papers = score_all(papers)
    gc = {"A":0,"B":0,"C":0,"D":0}
    for p in papers:
        g = (p.get("quality") or {}).get("grade","D")
        gc[g] = gc.get(g,0)+1
    emit(f"  🟢 A:{gc['A']}  🔵 B:{gc['B']}  🟡 C:{gc['C']}  🔴 D:{gc['D']}")
    results["stages"]["grade_counts"] = gc

    emit("\n━━ Stage 7 · Semantic Ranking ━━━━━━━━━━━━━━━━━━━━━━━━━")
    papers = semantic_rank(topic, papers, top_k=top_k)
    emit(f"  ✓ Top {len(papers)} selected")
    if papers: emit(f"  Top: {papers[0]['title'][:70]}")
    results["papers"] = papers

    emit("\n━━ Stage 8 · Summarization ━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    grade_order = ["A","B","C","D"]
    min_idx     = grade_order.index(min_grade)
    to_save     = [p for p in papers if grade_order.index((p.get("quality") or {}).get("grade","D"))<=min_idx]
    emit(f"  Summarising {len(to_save)} papers via {'Claude API' if anthropic_key else 'extractive'}")
    to_save = summarise_all(to_save, api_key=anthropic_key)
    save_titles  = {p["title"] for p in to_save}
    final_papers = to_save + [p for p in papers if p["title"] not in save_titles]

    emit("\n━━ Stage 9 · Writing Outputs ━━━━━━━━━━━━━━━━━━━━━━━━━━")
    emit(f"  📁 {md_dir}")
    emit(f"  🖼  {img_dir}")
    emit(f"  📋 {json_dir}")
    records = write_all(final_papers, md_dir, img_dir, json_dir, min_grade)
    emit(f"  ✓ Saved {len(records)} papers")
    results["records"] = records

    emit(f"\n━━ Done ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    emit(f"  Saved: {len(records)}   Skipped: {len(final_papers)-len(records)}")
    return results