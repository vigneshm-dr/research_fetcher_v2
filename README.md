# Research Fetcher v2

> A 10-stage intelligent pipeline for fetching, grading, classifying, and summarising medical research papers — built as a raw corpus builder for LLM knowledge wikis.

---

## Table of Contents

- [What This Does](#what-this-does)
- [Who This Is For](#who-this-is-for)
- [How It Works — The 10-Stage Pipeline](#how-it-works--the-10-stage-pipeline)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Keys](#api-keys)
- [Running the Pipeline](#running-the-pipeline)
- [Understanding the Output](#understanding-the-output)
- [Quality Grading System](#quality-grading-system)
- [Local LLM Support (Ollama)](#local-llm-support-ollama)
- [Data Sources](#data-sources)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## What This Does

Research Fetcher v2 takes a plain-English medical research topic and automatically:

1. Expands it into 6–8 targeted search queries across different clinical and methodological angles
2. Fetches matching papers from PubMed, medRxiv, and Semantic Scholar simultaneously
3. Removes duplicates across all three sources
4. Enriches each paper with citation counts and metadata
5. Classifies each paper by study type, evidence level, and clinical domain
6. Scores and grades each paper from A to D based on quality criteria
7. Ranks papers by relevance to your original topic using semantic similarity
8. Generates structured summaries with TL;DR, methods, results, and clinical implications
9. Saves everything as Markdown files, JSON records, and downloaded figures
10. Presents all results in a clean browser dashboard

The result is a structured, graded, summarised corpus of medical literature ready for LLM ingestion, clinical review, or knowledge base construction.

---

## Who This Is For

- **Clinicians** building evidence-based knowledge bases for AI assistants
- **Medical AI researchers** constructing training corpora for domain-specific LLMs
- **Healthcare organisations** automating literature surveillance on specific conditions
- **Students and residents** doing systematic topic reviews without manual database searching
- Anyone following the **Karpathy wiki model** — building a raw file repository that an LLM can read and reason over

---

## How It Works — The 10-Stage Pipeline

```
User Topic
    │
    ▼
Stage 1 ── Query Expansion
           Detects clinical domain (NLP / Imaging / Signals / Genomics / Clinical)
           Generates 6–8 sub-queries: core · method · systematic review ·
           AI variant · clinical · benchmark · synonym · MeSH term
    │
    ▼
Stage 2 ── Multi-Source Retrieval
           PubMed → abstract + full text via PMC where available
           medRxiv → recent preprints with keyword scoring
           Semantic Scholar → citation counts + open access PDF links
    │
    ▼
Stage 3 ── Deduplication
           DOI-first matching (exact)
           Title fingerprint fallback (normalised string comparison)
           Keeps the richest version: full text > abstract length > citations
    │
    ▼
Stage 4 ── Metadata Enrichment
           Fills missing citation counts via Semantic Scholar API
           Adds open access status, PDF URLs, publication types
    │
    ▼
Stage 5 ── Classification
           Study type: RCT · Systematic Review · Cohort · Technical · …
           Evidence level: Oxford CEBM 1a through 5
           Domain: NLP · Medical Imaging · Physiology · Genomics · …
           Clinical relevance: High · Medium · Low · Non-clinical
           Key finding: extracted from abstract
    │
    ▼
Stage 6 ── Quality Scoring
           7-criterion rubric scores each paper 0–100
           Grades: A (≥75) · B (≥55) · C (≥35) · D (<35)
    │
    ▼
Stage 7 ── Semantic Ranking
           TF-IDF cosine similarity between papers and original topic
           Blended 50/50 with quality score
           Selects top-K most relevant papers
    │
    ▼
Stage 8 ── Summarization
           TL;DR · Objective · Methods · Results · Conclusions
           Limitations · Clinical Implications · Key Terms
    │
    ▼
Stage 9 ── Output Writing
           .md file per paper (human-readable)
           .json file per paper (machine-readable)
           Images downloaded from PMC figures
           Rolling _corpus_index.json manifest
    │
    ▼
Stage 10 ── Dashboard
            Gradio web UI at http://localhost:7860
            Live run log · Results table · Corpus Explorer · JSON Export
```

---

## Project Structure

```
research_fetcher_v2/
│
├── app.py                      Stage 10: Gradio dashboard and UI
├── config.py                   All settings — paths, keys, thresholds
├── requirements.txt            Python dependencies
├── README.md                   This file
│
└── pipeline/
    ├── __init__.py             Package marker
    ├── utils.py                Shared helpers: HTTP, LLM caller, text utils
    ├── expander.py             Stage 1: Query expansion engine
    ├── retrieval.py            Stage 2: PubMed, medRxiv, Semantic Scholar
    ├── dedup_enrich.py         Stages 3+4: Deduplication and enrichment
    ├── classifier.py           Stage 5: Study type and domain classification
    ├── scorer_ranker.py        Stages 6+7: Quality scoring and semantic ranking
    ├── summarizer.py           Stage 8: Structured summarization
    ├── writer.py               Stage 9: Markdown, JSON, image output
    └── orchestrator.py         Wires all stages together, streams log lines
```

**One rule:** every file does exactly one job. If you need to change how papers are scored, you only touch `scorer_ranker.py`. If you need to add a new data source, you only touch `retrieval.py`. Nothing is tangled together.

---

## Quick Start

If you have Python 3.10+ and Ollama installed:

```bash
git clone https://github.com/YOUR_USERNAME/research_fetcher_v2.git
cd research_fetcher_v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama serve &
python3 app.py
```

Open `http://localhost:7860` in your browser, type a topic, click Run.

---

## Installation

### Requirements

- macOS (Apple Silicon or Intel) / Linux
- Python 3.10 or higher
- [Ollama](https://ollama.com) (optional — for local LLM features)
- Internet connection (for fetching papers)

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/research_fetcher_v2.git
cd research_fetcher_v2
```

### Step 2 — Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

You must activate the virtual environment every time you open a new terminal:

```bash
source .venv/bin/activate
```

Your prompt will show `(.venv)` when it is active.

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Create output folders

```bash
mkdir -p ~/llm_wiki/papers ~/llm_wiki/images ~/llm_wiki/json
```

### Step 5 — Set up Ollama (optional but recommended)

Ollama lets you run a local LLM for free. Without it the pipeline uses rule-based fallbacks for classification and summarisation. With it, you get genuine AI-powered analysis at no cost.

```bash
# Install Ollama
brew install ollama

# Pull a model — Mistral 7B is recommended for Apple Silicon
ollama pull mistral

# For best medical results, also pull Meditron
ollama pull meditron
```

Start Ollama automatically on every boot:

```bash
brew services start ollama
```

---

## Configuration

All settings live in `config.py`. Edit this file to change behaviour.

```python
# Where your output files are saved
DEFAULT_MD_DIR   = Path("~/llm_wiki/papers").expanduser()
DEFAULT_IMG_DIR  = Path("~/llm_wiki/images").expanduser()
DEFAULT_JSON_DIR = Path("~/llm_wiki/json").expanduser()

# How many papers to fetch per source per query
# Higher = more papers, slower run, better chance of finding A/B grades
DEFAULT_N_PER_SOURCE = 8

# Only save papers at or above this grade
# Use "C" if you have no API keys (most papers score C without full text)
# Use "B" if you have API keys and want higher quality only
DEFAULT_MIN_GRADE = "C"

# How many papers to keep after semantic ranking
SEMANTIC_TOP_K = 30
```

### Recommended settings by use case

| Use case | N per source | Min grade | Top K |
|---|---|---|---|
| Quick test | 2 | C | 10 |
| Daily literature check | 5 | B | 20 |
| Comprehensive topic sweep | 15 | C | 50 |
| Full corpus build | 20 | C | 100 |

---

## API Keys

All API keys are optional. The pipeline runs without any of them using rule-based fallbacks. Keys improve speed, quality, and access.

### NCBI API Key (PubMed)

**Effect:** Raises PubMed rate limit from 3 to 10 requests per second — makes fetching 3× faster.

**How to get it (free):**
1. Go to `https://www.ncbi.nlm.nih.gov/account/`
2. Create a free account
3. Click your username → Settings → API Key Management → Create an API Key

**How to set it:**
```bash
echo 'export NCBI_API_KEY=your_key_here' >> ~/.zshrc
source ~/.zshrc
```

### Semantic Scholar API Key

**Effect:** Removes the 100 requests per 5-minute cap that causes rate-limiting warnings in your run log.

**How to get it (free):**
1. Go to `https://www.semanticscholar.org/product/api`
2. Click Get Started → fill in the form (takes a few hours to receive)

**How to set it:**
```bash
echo 'export S2_API_KEY=your_key_here' >> ~/.zshrc
source ~/.zshrc
```

### Anthropic API Key (Claude)

**Effect:** Replaces local Ollama for AI stages. Claude Sonnet produces the highest quality query expansion, classification, and summarisation. Costs roughly $0.01–0.05 per full run.

**How to get it (paid):**
1. Go to `https://console.anthropic.com`
2. Sign up → API Keys → Create Key

**How to set it:**
```bash
echo 'export ANTHROPIC_API_KEY=your_key_here' >> ~/.zshrc
source ~/.zshrc
```

### Priority order

When running, the pipeline uses LLMs in this order:

```
Ollama running locally?
    YES → use best available local model (Meditron > Llama 3.1 > Mistral)
    NO  → Anthropic API key present?
              YES → use Claude Sonnet
              NO  → rule-based fallbacks (still works, lower quality)
```

---

## Running the Pipeline

### Option A — Gradio UI (recommended)

```bash
source .venv/bin/activate
python3 app.py
```

Open `http://localhost:7860` in your browser. You will see three tabs:

**Run tab:**
- Type your research topic
- Adjust sliders for results per source, minimum grade, and top-K
- Click Run Pipeline
- Watch the live log stream through all 9 stages
- Results appear in the table below sorted by quality score

**Corpus Explorer tab:**
- Browse all papers saved across all your previous runs
- Loads from `_corpus_index.json` — the rolling manifest

**Export JSON tab:**
- Exports the full corpus index as formatted JSON
- Ready to paste into an LLM context window or pipe into a vector database

### Option B — Terminal (for automation)

```bash
source .venv/bin/activate
python3 -c "
from pathlib import Path
from pipeline.orchestrator import run
run(
    topic         = 'ECG arrhythmia deep learning',
    n_per_source  = 5,
    min_grade     = 'C',
    top_k         = 30,
    md_dir        = Path('~/llm_wiki/papers').expanduser(),
    img_dir       = Path('~/llm_wiki/images').expanduser(),
    json_dir      = Path('~/llm_wiki/json').expanduser(),
    emit          = print,
)
"
```

---

## Understanding the Output

After a run, three types of files are created:

### Markdown files — `~/llm_wiki/papers/`

One `.md` file per saved paper. Human-readable, renderable in any Markdown viewer or Obsidian vault. Each file contains:

```
# Paper Title

> Grade badge · Study type · Evidence level · Domain

## Metadata
Source, Year, Authors, Venue, Citations, DOI, URL, Topics, Key Finding

## Quality Breakdown
Score breakdown across all 7 criteria

## Summary
TL;DR · Objective · Methods · Results · Conclusions · Clinical Implications

## Abstract
Full abstract text

## Full Text
Section-by-section content (where PMC full text was available)

## Figures
Downloaded images with captions
```

### JSON files — `~/llm_wiki/json/`

One `.json` per paper plus a rolling `_corpus_index.json`. The JSON records contain every field in structured form — ready for vector database ingestion, LLM context injection, or downstream analysis.

### Images — `~/llm_wiki/images/`

Figures downloaded from PMC open-access papers. Named as `paper_slug__figure_name.jpg`. Referenced by relative path in the corresponding Markdown file.

---

## Quality Grading System

Every paper is scored out of 100 across 7 criteria:

| Criterion | Max score | How it is calculated |
|---|---|---|
| Recency | 20 | 20 − (2 × years since publication). Zero for papers older than 10 years. |
| Citations | 25 | citation count ÷ 5, capped at 25. 125+ citations = full score. |
| Evidence level | 15 | Oxford CEBM scale. Systematic reviews of RCTs score 15. Expert opinion scores 1. |
| Full text | 15 | 15 if PMC full text retrieved, 0 if abstract only. |
| Abstract quality | 10 | abstract length ÷ 50, capped at 10. Proxy for detail and completeness. |
| Open access | 8 | 8 if freely available, 0 if paywalled. |
| Venue prestige | 7 | 7 for Nature, Lancet, NEJM, JAMA, BMJ, NeurIPS, etc. 3 for all others. |

**Grade thresholds:**

| Grade | Score | Meaning |
|---|---|---|
| A | 75–100 | Recent, well-cited, full text available, high-impact venue |
| B | 55–74 | Good quality — solid citations, open access, reasonable evidence level |
| C | 35–54 | Moderate — older or paywalled or low citations but useful content |
| D | 0–34 | Low quality — very old, no abstract, no citations, or expert opinion only |

**Important:** most papers score C without API keys because paywalled papers lose 23 points immediately (no full text + not open access). Set `DEFAULT_MIN_GRADE = "C"` in `config.py` to save these papers.

---

## Local LLM Support (Ollama)

The pipeline integrates with Ollama for three AI-powered stages:

### Stage 1 — Query Expansion

Without LLM: generates 6–8 queries using keyword templates and synonym tables.

With LLM: sends your topic to the model and asks it to generate targeted clinical sub-queries with rationale for each angle — understanding context, synonyms, and methodological nuance automatically.

### Stage 5 — Classification

Without LLM: uses ordered regex rules to detect study type from title and abstract. Works well for obvious cases but misclassifies mixed-method papers.

With LLM: sends title and abstract to the model and asks for structured classification — study type, evidence level, domain, clinical relevance, and key finding in one pass.

### Stage 8 — Summarization

Without LLM: extracts sentences by position (first = objective, last 2 = conclusions).

With LLM: reads the full abstract and any available full text sections, then generates a rewritten structured summary in clinical language.

### Model selection

The pipeline automatically selects the best available Ollama model in this order:

```
meditron:7b  →  fine-tuned on PubMed, best for medical papers
llama3.1:8b  →  strongest general reasoning
llama3:8b    →  good general model
mistral:7b   →  fast, reliable, recommended for Apple Silicon
```

To see which model is being used:

```bash
python3 -c "from pipeline.utils import _get_ollama_model; print(_get_ollama_model())"
```

### Recommended models by hardware

| Mac | Recommended model | RAM used |
|---|---|---|
| M1 8GB | mistral:7b | 4.5 GB |
| M1 16GB | meditron:7b | 4.5 GB |
| M2/M3 16GB+ | llama3.1:8b | 5.5 GB |

---

## Data Sources

### PubMed / PubMed Central

- The gold standard biomedical database with 35+ million citations
- Full text available for open-access papers via PMC
- Figures and structured sections extracted from PMC XML
- Rate limit: 3 req/s without key, 10 req/s with NCBI key

### medRxiv

- Health sciences preprint server — papers before peer review
- Covers all medical specialities and public health
- 100% open access — every paper is freely available
- Note: preprints are not peer-reviewed. Labelled as such in classification.
- The pipeline scans recent papers by date and scores by keyword match

### Semantic Scholar

- Covers 200+ million papers across all fields
- Provides citation counts, open access status, and PDF links
- Also used in Stage 4 to enrich PubMed and medRxiv papers with citations
- Rate limit: 100 req/5 min without key, 1 req/s with S2 key

---

## Troubleshooting

### Zero papers saved

**Cause:** All papers scored below your minimum grade threshold.

**Fix:** Change `DEFAULT_MIN_GRADE` to `"C"` in `config.py` and rerun.

```bash
python3 -c "
content = open('config.py').read()
open('config.py','w').write(content.replace(
    'DEFAULT_MIN_GRADE    = \"B\"',
    'DEFAULT_MIN_GRADE    = \"C\"'
))
print('Done')
"
```

### medRxiv returns no papers

**Cause:** Your search terms are shorter than 4 characters and get filtered out (e.g. "ECG" has 3 characters).

**Fix:** Use full terms in your topic — "electrocardiogram arrhythmia deep learning" instead of "ECG arrhythmia deep learning".

### Rate-limiting warnings in the log

**Cause:** Semantic Scholar free tier limits to 100 requests per 5 minutes.

**Fix:** Get a free Semantic Scholar API key and set it in your environment. The warnings are harmless — the pipeline retries automatically.

### Ollama not detected

**Cause:** Ollama server is not running.

**Fix:**
```bash
ollama serve
```
Or to start permanently:
```bash
brew services start ollama
```

### ModuleNotFoundError for gradio / requests

**Cause:** Virtual environment is not activated.

**Fix:**
```bash
source .venv/bin/activate
```

### git push asks for password and fails

**Cause:** GitHub no longer accepts account passwords for git push.

**Fix:** Create a Personal Access Token at `github.com → Settings → Developer settings → Personal access tokens → Generate new token`. Use this token as your password when git push prompts you.

---

## Known Limitations

**No caching between stages.** If the pipeline crashes at Stage 8 after fetching 200 papers, you restart from Stage 1. All network calls repeat.

**Sequential retrieval.** PubMed, medRxiv, and Semantic Scholar are called one after another, not in parallel. A full run with 8 queries can take 10–20 minutes.

**medRxiv has no keyword search.** The API only serves papers in chronological order. The pipeline scans 500 recent papers by default and scores by keyword match. Older papers on your topic will not be found.

**Full text only for open-access papers.** NEJM, Lancet, JAMA, and most clinical journals are paywalled. These papers lose 23 quality points and are often graded C/D despite being high-impact.

**TF-IDF ranking has no medical vocabulary.** "Cardiac" and "heart" score zero similarity. Papers using different terminology for the same concept may rank low.

**Preprints score poorly on citations.** A 2024 medRxiv preprint with 0 citations scores low even if the research is excellent. This is a known bias of citation-based quality scoring.

---

## Roadmap

Features planned for future versions:

- Checkpoint caching after retrieval so crashes do not lose fetched papers
- Parallel retrieval using ThreadPoolExecutor to reduce run time
- Biomedical sentence embeddings (PubMedBERT) to replace TF-IDF ranking
- Citation velocity scoring to surface seminal older papers
- BioRxiv support alongside medRxiv
- Gradio live log streaming (currently updates only when run completes)
- Scheduled runs via cron for daily literature surveillance
- Export to Obsidian vault format with bidirectional links between papers

---

## Licence

MIT — free to use, modify, and distribute for any purpose.

---

*Built by Vignesh — research corpus tooling for medical AI development.*
