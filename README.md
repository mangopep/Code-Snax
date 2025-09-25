# 🍿 Code-Snax

> Snack-sized coding notes with AI summaries + Notion links.  
> Because algorithms shouldn’t feel like a 500-page textbook. 🌯

---

## 📖 Notes Index (auto-updated)

<!-- SNAX-START -->
*(Run the action or push with links to generate this section.)*
<!-- SNAX-END -->

---

## 🚀 What is this?
- I write full problem notes in **Notion**.
- This repo **auto-updates** with a short, friendly **AI summary** + the **Notion link**.
- Vibes: simple, human, GenZ-friendly.

## 🛠 How it works (no Notion API)
1. I paste public **Notion share links** into `notion_links.txt` (one per line).
2. A GitHub Action runs a Python script that:
   - Scrapes the public page (title + text)
   - Summarizes with **Cohere**
   - Updates this README between the markers

## 🧩 Add a new note
- Put the share URL in `notion_links.txt`
- Commit & push
- The Action updates this page automatically

## ⭐ Support
If you like this idea, drop a star. Let’s make problem-solving snack-sized.
