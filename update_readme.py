import os
import re
import json
import hashlib
import time
from typing import List, Tuple, Dict

import requests
from bs4 import BeautifulSoup

README_PATH = "README.md"
LINKS_PATH = "notion_links.txt"
CACHE_PATH = "summaries.json"
MAX_CHARS_FOR_AI = 3500
SECTION_START = "<!-- SNAX-START -->"
SECTION_END = "<!-- SNAX-END -->"
REQUEST_TIMEOUT = 20
USER_AGENT = "CodeSnaxBot/1.0 (+https://github.com/)"

COHERE_API_KEY = os.getenv("COHERE_API_KEY")

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
    seen, uniq = set(), []
    for u in links:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq


def fetch_notion_public(url: str) -> Tuple[str, str]:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Title
    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"]
    if not title and soup.title:
        title = soup.title.get_text(strip=True)
    title = (title or "Untitled").strip()

    # Content
    blocks = []
    for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "blockquote"]):
        txt = tag.get_text(" ", strip=True)
        if txt:
            blocks.append(txt)

    text = " \n".join(blocks)
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
    if not COHERE_API_KEY:
        return "AI TL;DR: (No API key set) Summary unavailable.\nSnack-take: (—)"
    try:
        import cohere
        co = cohere.Client(COHERE_API_KEY)

        prompt = f"{SUMMARY_INSTRUCTIONS}\n\n---\n{text[:MAX_CHARS_FOR_AI]}"

        # ✅ Use new Chat API
        resp = co.chat(
            model="command-r-plus",
            message=prompt,
            temperature=0.4,
        )

        out = resp.text.strip()
        return out if out else "AI TL;DR: (empty)\nSnack-take: (—)"

    except Exception as e:
        return f"AI TL;DR: (Cohere chat error: {e})\nSnack-take: (—)"


def render_card(title: str, url: str, ai_summary: str) -> str:
    if "AI TL;DR:" not in ai_summary:
        ai_summary = "AI TL;DR: " + ai_summary
    lines = ai_summary.strip().splitlines()
    tldr = lines[0] if lines else "AI TL;DR: (empty)"
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
        block = f"{SECTION_START}\n{cards_md.strip()}\n{SECTION_END}"
        readme = readme.strip() + "\n\n## 📖 Notes Index\n\n" + block + "\n"
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
    print(f"🔗 Links loaded: {links}")
    if not links:
        print("⚠️ No links in notion_links.txt")
        return

    cache = load_cache(CACHE_PATH)
    cards = []

    for url in links:
        print(f"\n[•] Processing: {url}")
        try:
            title, content = fetch_notion_public(url)
            print(f"  - Title: {title}")
            print(f"  - Content length: {len(content)} chars")
            if not content:
                ai_summary = "AI TL;DR: (No content scraped – check if link is public!)\nSnack-take: (—)"
            else:
                h = content_hash(content)
                cached = cache.get(url, {})
                if cached.get("hash") == h and cached.get("summary"):
                    ai_summary = cached["summary"]
                    print("  - Using cached summary.")
                else:
                    ai_summary = cohere_summarize(content)
                    cache[url] = {
                        "hash": h,
                        "title": title,
                        "summary": ai_summary,
                        "ts": int(time.time())
                    }
                    print("  - Generated new summary.")
        except Exception as e:
            print(f"  - Fetch error: {e}")
            title = "Fetch failed"
            ai_summary = f"AI TL;DR: (Fetch error: {e})\nSnack-take: (—)"

        cards.append(render_card(title, url, ai_summary))

    save_cache(CACHE_PATH, cache)
    cards_md = "".join(cards).strip() if cards else "*No notes yet.*"
    update_readme_block(cards_md)
    print("\n✅ Done. README updated.")


if __name__ == "__main__":
    main()
