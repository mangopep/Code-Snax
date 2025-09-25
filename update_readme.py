import os
import re

README_PATH = "README.md"
LINKS_PATH = "notion_links.txt"
SECTION_START = "<!-- SNAX-START -->"
SECTION_END = "<!-- SNAX-END -->"

def read_links(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]

def render_table(links):
    if not links:
        return "*No notes yet.*"

    # Markdown table header
    table = ["| # | Note Link |", "|---|-----------|"]

    for i, url in enumerate(links, start=1):
        table.append(f"| {i} | [Notion Note {i}]({url}) |")

    return "\n".join(table)

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
    print(f"🔗 Found {len(links)} links")
    cards_md = render_table(links)
    update_readme_block(cards_md)
    print("✅ README updated with links table.")

if __name__ == "__main__":
    main()
