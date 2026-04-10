import os, json, logging
from pathlib import Path
import gradio as gr
from config import (DEFAULT_MD_DIR, DEFAULT_IMG_DIR, DEFAULT_JSON_DIR,
                    DEFAULT_N_PER_SOURCE, DEFAULT_MIN_GRADE, SEMANTIC_TOP_K,
                    ANTHROPIC_API_KEY, NCBI_API_KEY, S2_API_KEY)
from pipeline.orchestrator import run as run_pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

def load_corpus_index(json_dir):
    p = Path(json_dir).expanduser()/"_corpus_index.json"
    if not p.exists(): return []
    try: return json.loads(p.read_text())
    except Exception: return []

def records_to_table(records):
    rows = []
    for r in records:
        rows.append([r.get("title","")[:70], r.get("source",""),
                     str(r.get("year","")),
                     r.get("quality",{}).get("grade","?"),
                     r.get("quality",{}).get("score",0),
                     r.get("classification",{}).get("study_type","?"),
                     r.get("classification",{}).get("domain","?"),
                     r.get("citations",0),
                     f"{r.get('semantic_score',0):.3f}",
                     "✅" if r.get("has_full_text") else "❌"])
    return sorted(rows, key=lambda x: x[4], reverse=True)

def run_with_stream(topic, n_per, min_grade, top_k,
                    md_dir_str, img_dir_str, json_dir_str,
                    ant_key, ncbi_key, s2_key):
    log_lines = []
    def emit(msg): log_lines.append(msg)
    try:
        results = run_pipeline(
            topic=topic, n_per_source=int(n_per), min_grade=min_grade,
            md_dir=Path(md_dir_str).expanduser(),
            img_dir=Path(img_dir_str).expanduser(),
            json_dir=Path(json_dir_str).expanduser(),
            anthropic_key=ant_key.strip(), ncbi_key=ncbi_key.strip(), s2_key=s2_key.strip(),
            top_k=int(top_k), emit=emit,
        )
        return "\n".join(log_lines), records_to_table(results.get("records",[])), \
               f"✅ {len(results.get('records',[]))} papers saved."
    except Exception as e:
        import traceback
        return traceback.format_exc(), [], "❌ Error — check log."

def refresh_explorer(json_dir_str):
    records = load_corpus_index(json_dir_str)
    return records_to_table(records), f"{len(records)} papers in index."

def export_json(json_dir_str):
    return json.dumps(load_corpus_index(json_dir_str), indent=2, ensure_ascii=False)

with gr.Blocks(title="Research Fetcher v2", theme=gr.themes.Soft()) as app:
    gr.Markdown("# Research Fetcher v2 — 10-Stage Pipeline")

    with gr.Tabs():
        with gr.Tab("Run"):
            with gr.Row():
                with gr.Column(scale=3):
                    topic_box = gr.Textbox(label="Research Topic", lines=2,
                        placeholder="e.g.  transformer ECG arrhythmia detection")
                    with gr.Row():
                        n_per  = gr.Slider(1, 20, value=DEFAULT_N_PER_SOURCE, step=1,
                                           label="Results per source per query")
                        min_g  = gr.Dropdown(["A","B","C","D"], value=DEFAULT_MIN_GRADE,
                                             label="Min grade to save")
                        top_k  = gr.Slider(5, 100, value=SEMANTIC_TOP_K, step=5,
                                           label="Top-K after ranking")
                with gr.Column(scale=2):
                    gr.Markdown("### API Keys (all optional)")
                    ant_key  = gr.Textbox(label="Anthropic", value=ANTHROPIC_API_KEY, type="password")
                    ncbi_key = gr.Textbox(label="NCBI",      value=NCBI_API_KEY,      type="password")
                    s2_key   = gr.Textbox(label="Semantic Scholar", value=S2_API_KEY, type="password")
            with gr.Row():
                md_dir   = gr.Textbox(label="Markdown folder", value=str(DEFAULT_MD_DIR))
                img_dir  = gr.Textbox(label="Images folder",   value=str(DEFAULT_IMG_DIR))
                json_dir = gr.Textbox(label="JSON folder",     value=str(DEFAULT_JSON_DIR))
            run_btn = gr.Button("Run Pipeline", variant="primary", size="lg")
            status  = gr.Textbox(label="Status", interactive=False, lines=1)
            log_box = gr.Textbox(label="Log", lines=30, interactive=False)
            result_table = gr.Dataframe(
                headers=["Title","Source","Year","Grade","Score",
                         "Study Type","Domain","Citations","Sem.Score","Full Text"],
                label="Results", interactive=False, wrap=True)
            run_btn.click(
                fn=run_with_stream,
                inputs=[topic_box, n_per, min_g, top_k,
                        md_dir, img_dir, json_dir, ant_key, ncbi_key, s2_key],
                outputs=[log_box, result_table, status])

        with gr.Tab("Corpus Explorer"):
            exp_json_dir = gr.Textbox(label="JSON folder", value=str(DEFAULT_JSON_DIR))
            refresh_btn  = gr.Button("Refresh")
            exp_status   = gr.Textbox(interactive=False, lines=1)
            exp_table    = gr.Dataframe(
                headers=["Title","Source","Year","Grade","Score",
                         "Study Type","Domain","Citations","Sem.Score","Full Text"],
                interactive=False, wrap=True)
            refresh_btn.click(fn=refresh_explorer,
                              inputs=[exp_json_dir],
                              outputs=[exp_table, exp_status])

        with gr.Tab("Export JSON"):
            exp2_dir   = gr.Textbox(label="JSON folder", value=str(DEFAULT_JSON_DIR))
            export_btn = gr.Button("Export corpus index")
            json_out   = gr.Code(label="JSON", language="json", lines=40)
            export_btn.click(fn=export_json, inputs=[exp2_dir], outputs=[json_out])

if __name__ == "__main__":
    app.launch(share=False, inbrowser=True)
