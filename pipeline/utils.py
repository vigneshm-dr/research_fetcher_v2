import re, json, time, logging
import requests

log = logging.getLogger("rfetcher")

def safe_get(url, params=None, timeout=20, retries=2, headers=None, **kwargs):
    default_headers = {"User-Agent": "ResearchFetcher/2.0"}
    if headers:
        default_headers.update(headers)
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                             headers=default_headers, **kwargs)
            r.raise_for_status()
            return r
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                wait = 2 ** attempt
                log.warning(f"Rate-limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                log.warning(f"HTTP error: {e}")
                return None
        except Exception as e:
            log.warning(f"Request failed ({attempt+1}): {url} -> {e}")
            if attempt < retries:
                time.sleep(1)
    return None

def slugify(text, maxlen=60):
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower())[:maxlen].strip("_") or "unknown"

def xml_text(el):
    return "".join(el.itertext()).strip() if el is not None else ""

def truncate(text, chars=3000):
    return text[:chars] + "..." if len(text) > chars else text

def parse_json_response(text):
    text = re.sub(r"```(?:json)?", "", text).strip().strip("`").strip()
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        idx = text.find(start_char)
        if idx != -1:
            try:
                return json.loads(text[idx:text.rfind(end_char)+1])
            except json.JSONDecodeError:
                pass
    return None

def claude_call(prompt, system="", api_key="",
                model="claude-sonnet-4-20250514", max_tokens=1024):
    """
    Unified LLM caller. Priority order:
      1. Local Ollama (if running) — free, private, no key needed
      2. Anthropic API (if api_key provided) — cloud, costs money
      3. None — falls back to rule-based in each stage
    """
    # Try Ollama first
    if _ollama_running():
        result = _ollama_call(prompt, system)
        if result:
            return result

    # Fall back to Anthropic if key provided
    if api_key:
        return _anthropic_call(prompt, system, api_key, model, max_tokens)

    return None

def _ollama_running():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

def _get_ollama_model():
    """Pick the best available model — prefer medical, fall back to general."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code != 200:
            return None
        models = [m["name"] for m in r.json().get("models", [])]
        # Priority order: medical first, then general
        preferred = [
            "meditron:7b", "meditron",
            "llama3.1:8b", "llama3.1",
            "llama3:8b",   "llama3",
            "mistral:7b",  "mistral",
            "phi3",        "gemma",
        ]
        for p in preferred:
            for m in models:
                if m.startswith(p):
                    return m
        return models[0] if models else None
    except Exception:
        return None

def _ollama_call(prompt, system=""):
    model = _get_ollama_model()
    if not model:
        return None
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        r = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        text = r.json().get("message", {}).get("content", "")
        log.info(f"Ollama ({model}) responded: {len(text)} chars")
        return text if text else None
    except Exception as e:
        log.warning(f"Ollama call failed: {e}")
        return None

def _anthropic_call(prompt, system="", api_key="",
                    model="claude-sonnet-4-20250514", max_tokens=1024):
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          json=body, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except Exception as e:
        log.warning(f"Anthropic API error: {e}")
        return None
