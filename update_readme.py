import os
import re
import json
import hashlib
import time
from typing import List, Tuple, Dict

import requests
from bs4 import BeautifulSoup

# ====== CONFIG ======
README_PATH = "README.md"
LINKS_PATH = "notion_links.txt"
CACHE_PATH = "summaries.json"        # created automatically
MAX_CHARS_FOR_AI = 3500              # trim long pages before sending to AI
SECTION_START = "<!-- SNAX-START -->"
SECTION_END = "<!-- SNAX-END -->"
REQUEST_TIMEOUT = 20
USER_AGENT = "CodeSnaxBot/1.0 (+https://github.com/)"

# ====== COHERE ======
# Set COHERE_API_KEY in GitHub Secrets or your local env
COHERE_API_KEY = os.getenv("COHERE_API_KEY")

# If you prefer, you can tweak the prompt "style" here
SUMMARY_INSTRUCTIONS = (
    "You are writing for non-nerds and GenZ. Summarize this note in 1–3 short,"
    " clear sentences. Avoid jargon. Prefer stories or everyday analogies.\n"
    "Then add an optional 'Snack-take' line: a playful analogy in 5–12 words.\n"
    "Output format exactly:\n"
    "AI TL;DR: <1-3 sentences>\n"
    "Snack-take: <analogy line>  (omit this line if none)"
)

def read_links(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        links = [ln.strip() for ln in f if ln.strip()]
    # de-duplicate while preserving order
    seen = set()
    uniq = []
    for u in links:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq

def fetch_notion_public(url: str) -> Tuple[str, str]:
    """Fetch a public Notion share page and extract title + text content."""
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Title fallback chain
    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"]
    if not title and soup.title:
        title = soup.title.get_text(strip=True)
    title = (title or "Untitled").strip()

    # Collect visible text from typical Notion-exported tags
    # Keep it simple and robust; avoid script/style
    blocks = []
    for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "blockquote", "pre", "code"]):
        txt = tag.get_text(" ", strip=True)
        if txt:
            blocks.append(txt)

    # Join and lightly clean
    text = " \n".join(blocks)
    # Remove extra whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return title, text

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load_cache(path: str) -> Dict[str, dict]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(path: str, data: Dict[str, dict]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def cohere_summarize(text: str) -> str:
    """Use Cohere to produce the friendly summary. Requires COHERE_API_KEY."""
    if not COHERE_API_KEY:
        # Friendly fallback if the key is missing
        return "AI TL;DR: (No Cohere key found) Short summary unavailable.\nSnack-take: Add COHERE_API_KEY to run AI."
    try:
        # Cohere Python SDK
        import cohere  # type: ignore
        co = cohere.Client(COHERE_API_KEY)

        # Prefer the summarize endpoint if available; otherwise, generate()
        # Try summarize first
        try:
            resp = co.summarize(
                text=text,
                length="medium",
                format="paragraph",
                model="summarize-xlarge",
                temperature=0.3,
                additional_command=SUMMARY_INSTRUCTIONS
            )
            return f"AI TL;DR: {resp.summary.strip()}\nSnack-take: (auto)"
        except Exception:
            # Fall back to generate with a custom prompt
            prompt = f"{SUMMARY_INSTRUCTIONS}\n\n---\n{text[:MAX_CHARS_FOR_AI]}"
            resp = co.generate(
                model="command",
                prompt=prompt,
                max_tokens=180,
                temperature=0.4
            )
            out = resp.generations[0].text.strip()
            return out if out else "AI TL;DR: (empty)\nSnack-take: (none)"
    except Exception as e:
        return f"AI TL;DR: (Cohere error) {e}\nSnack-take: (none)"

def clip_for_ai(text: str) -> str:
    if len(text) <= MAX_CHARS_FOR_AI:
        return text
    return text[:MAX_CHARS_FOR_AI]

def render_card(title: str, url: str, ai_summary: str) -> str:
    # Ensure summary has the two labeled lines; if not, wrap it
    if "AI TL;DR:" not in ai_summary:
        ai_summary = "AI TL;DR: " + ai_summary
    lines = ai_summary.strip().splitlines()
    tldr = lines[0].strip() if lines else "AI TL;DR: (empty)"
    snack = None
    for ln in lines[1:]:
        if ln.lower().startswith("snack-take:"):
            snack = ln
            break
    if not snack:
        snack = "Snack-take: (—)"

    return (
        f"### 🔗 {title}\n"
        f"- Notion: {url}\n"
        f"- 📝 {tldr}\n"
        f"- 🍪 {snack}\n\n"
    )

def update_readme_block(cards_md: str) -> None:
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    if SECTION_START not in readme or SECTION_END not in readme:
        # Create section if missing
        block = f"{SECTION_START}\n{cards_md.strip()}\n{SECTION_END}"
        readme = readme.strip() + "\n\n## 📖 Notes Index (auto-updated)\n\n" + block + "\n"
    else:
        pattern = re.compile(
            re.escape(SECTION_START) + r".*?" + re.escape(SECTION_END),
            flags=re.DOTALL
        )
        replacement = f"{SECTION_START}\n{cards_md.strip()}\n{SECTION_END}"
        readme = pattern.sub(replacement, readme)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)

def main():
    links = read_links(LINKS_PATH)
    if not links:
        print("No links found in notion_links.txt — nothing to do.")
        return

    cache = load_cache(CACHE_PATH)
    cards = []

    for url in links:
        print(f"\n[•] Processing: {url}")
        try:
            title, content = fetch_notion_public(url)
        except Exception as e:
            print(f"  - Fetch error, skipping: {e}")
            continue

        # Hash content to avoid re-summarizing unchanged pages
        h = content_hash(content)
        cached = cache.get(url, {})
        if cached.get("hash") == h and cached.get("summary"):
            ai_summary = cached["summary"]
            print("  - Using cached summary.")
        else:
            text_for_ai = clip_for_ai(content)
            ai_summary = cohere_summarize(text_for_ai)
            cache[url] = {"hash": h, "title": title, "summary": ai_summary, "ts": int(time.time())}
            print("  - Generated new summary.")

        # Always prefer latest title scraped
        cache[url]["title"] = title

        cards.append(render_card(title, url, ai_summary))

    # Save cache before writing README
    save_cache(CACHE_PATH, cache)

    # Assemble cards and update README section
    cards_md = "".join(cards).strip() if cards else "*No notes yet.*"
    update_readme_block(cards_md)

    print("\nDone. README updated.")

if __name__ == "__main__":
    main()
