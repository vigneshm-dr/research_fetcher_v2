import os
from pathlib import Path

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NCBI_API_KEY      = os.getenv("NCBI_API_KEY", "")
S2_API_KEY        = os.getenv("S2_API_KEY", "")

DEFAULT_MD_DIR   = Path("~/llm_wiki/papers").expanduser()
DEFAULT_IMG_DIR  = Path("~/llm_wiki/images").expanduser()
DEFAULT_JSON_DIR = Path("~/llm_wiki/json").expanduser()

DEFAULT_N_PER_SOURCE = 8
DEFAULT_MIN_GRADE    = "B"
CLAUDE_MODEL         = "claude-sonnet-4-20250514"
SEMANTIC_TOP_K       = 30

STUDY_TYPES = [
    "Randomised Controlled Trial", "Systematic Review", "Meta-Analysis",
    "Cohort Study", "Case-Control Study", "Cross-Sectional Study",
    "Case Series / Report", "Review / Narrative Review",
    "Editorial / Commentary", "Technical / Methods Paper", "Preprint", "Other",
]

PRESTIGE_VENUES = {
    "nature", "cell", "lancet", "nejm", "new england journal",
    "jama", "bmj", "science", "plos", "pubmed central",
    "annals", "circulation", "gastroenterology", "radiology",
    "neurips", "icml", "iclr", "acl", "emnlp", "cvpr",
    "nature medicine", "npj", "elife",
}
