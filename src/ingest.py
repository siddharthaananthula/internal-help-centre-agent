from __future__ import annotations

import argparse
import csv
import html as html_lib
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait

import ssl_bootstrap  # noqa: F401


ROOT = Path(__file__).resolve().parents[1]
URL_CSV = ROOT / "eval" / "article_urls.csv"
RAW_DIR = ROOT / "data" / "raw"
CHUNK_FILE = ROOT / "data" / "chunks.jsonl"
USER_AGENT = "SuperloopInternalHelpAgent/0.1 (portfolio project; polite public-article research)"
HEADERS = {"User-Agent": USER_AGENT}
ROBOTS_URL = "https://support.superloop.com/robots.txt"
DELAY_SECONDS = 2.2


def robots_parser(robots_text: str) -> RobotFileParser:
    parser = RobotFileParser()
    parser.parse(robots_text.splitlines())
    return parser


def disallowed_urls(robots_text: str, urls: list[str]) -> list[str]:
    parser = robots_parser(robots_text)
    return [url for url in urls if not parser.can_fetch(USER_AGENT, url)]


def check_robots(urls: list[str]) -> None:
    """Stop before any article fetch if robots.txt disallows a listed URL."""
    response = requests.get(ROBOTS_URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    blocked = disallowed_urls(response.text, urls)
    if blocked:
        raise SystemExit("robots.txt disallows these URLs, stopping: " + ", ".join(blocked))
    time.sleep(DELAY_SECONDS)


def clean_article(html: str, url: str) -> tuple[str, str, list[dict[str, str]]]:
    def normalise(text: str) -> str:
        text = html_lib.unescape(text)
        text = unicodedata.normalize("NFKC", text)
        text = text.replace("�", "'")
        text = text.replace("\u2013", "-").replace("\u2014", "-")
        text = re.sub(r"(\d+)\s*'\s*(\d+)", r"\1-\2", text)
        text = re.sub(r"\ufffds\b", "'s", text)
        text = re.sub(r"\ufffdre\b", "'re", text)
        text = re.sub(r"\ufffdt\b", "'t", text)
        text = re.sub(r"\ufffdll\b", "'ll", text)
        text = re.sub(r"\ufffdve\b", "'ve", text)
        text = re.sub(r"\ufffd", "", text)
        text = text.replace("’", "'").replace("‘", "'")
        text = text.replace("“", '"').replace("”", '"')
        text = re.sub(r"(?<=\w)'(?=\w)", "'", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def split_words(text: str, target: int = 320, overlap: int = 50) -> list[str]:
        words = text.split()
        if len(words) <= 400:
            return [" ".join(words)]
        chunks: list[str] = []
        start = 0
        while start < len(words):
            end = min(start + target, len(words))
            chunks.append(" ".join(words[start:end]))
            if end == len(words):
                break
            start = end - overlap
        return chunks

    def text_with_list_separators(node: BeautifulSoup) -> str:
        for br in node.select("br"):
            br.replace_with(" ; ")
        for item in node.select("li"):
            item.insert_before(" ; ")
            item.insert_after(" ; ")
        text = node.get_text(" ", strip=True)
        text = re.sub(r"\s*;\s*", "; ", text)
        return re.sub(r"\s+", " ", text).strip()

    def merge_short_sections(sections: list[dict[str, str]]) -> list[dict[str, str]]:
        merged: list[dict[str, str]] = []
        for section in sections:
            words = len(section["text"].split())
            if merged and words < 150:
                merged[-1]["text"] = merged[-1]["text"] + " " + section["text"]
                continue
            merged.append(section.copy())
        return merged

    def merge_chunks_under_40(chunks: list[dict[str, str]]) -> list[dict[str, str]]:
        merged = [chunk.copy() for chunk in chunks]
        index = 0
        while index < len(merged):
            if len(merged[index]["text"].split()) < 40:
                if index + 1 < len(merged):
                    merged[index + 1]["text"] = merged[index]["text"] + " " + merged[index + 1]["text"]
                    merged[index + 1]["section"] = merged[index]["section"] if merged[index]["section"] != "Introduction" else merged[index + 1]["section"]
                    del merged[index]
                    continue
                if index > 0:
                    merged[index - 1]["text"] = merged[index - 1]["text"] + " " + merged[index]["text"]
                    del merged[index]
                    continue
            index += 1
        return merged

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script, style, nav, header, footer, form, aside"):
        tag.decompose()

    title_tag = soup.select_one("h1") or soup.title
    title = normalise(title_tag.get_text(" ", strip=True)) if title_tag else url.rsplit("/", 1)[-1]
    title = title.replace("\ufffd", "").strip()
    title = re.sub(r"\bHere.s\b", "Here's", title)

    rich_text = soup.select("lightning-formatted-rich-text")
    content = soup.select_one("main") \
        or soup.select_one('[role="main"]') \
        or soup.select_one(".slds-rich-text") \
        or soup.select_one("article") \
        or soup.body \
        or soup

    chunks: list[dict[str, str]] = []
    if rich_text:
        rich_text_node = max(rich_text, key=lambda element: len(element.get_text(" ", strip=True)))
        rich_text_node = BeautifulSoup(str(rich_text_node), "html.parser")
        text = normalise(text_with_list_separators(rich_text_node))
        text = re.sub(r"\bHere.s\b", "Here's", text)
        text = re.sub(r"\ufffd", "", text)
        heading_candidates: list[str] = []
        for heading in soup.select("h2"):
            candidate = normalise(heading.get_text(" ", strip=True))
            candidate = re.sub(r"\bHere.s\b", "Here's", candidate)
            if candidate and candidate.lower() != title.lower() and len(candidate) <= 120:
                if candidate not in heading_candidates:
                    heading_candidates.append(candidate)

        positions: list[tuple[int, str]] = []
        for candidate in heading_candidates:
            for match in re.finditer(re.escape(candidate), text, flags=re.IGNORECASE):
                positions.append((match.start(), candidate))
                break
        positions.sort()
        if positions:
            sections: list[dict[str, str]] = []
            for index, (start, heading) in enumerate(positions):
                end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
                section_text = normalise(text[start:end])
                if section_text.lower().startswith(heading.lower()):
                    section_text = section_text[len(heading):].strip(" :-")
                while section_text.lower().startswith(heading.lower()):
                    section_text = section_text[len(heading):].strip(" :-")
                if len(section_text.split()) >= 10:
                    sections.append({"section": heading, "text": section_text})
        else:
            sections = [{"section": "Introduction", "text": text}]

        if not sections:
            sections = [{"section": "Introduction", "text": text}]

        for section in merge_short_sections(sections):
            for part in split_words(section["text"]):
                chunks.append({"section": section["section"], "text": normalise(part)})
        chunks = merge_chunks_under_40([chunk for chunk in chunks if len(chunk["text"].split()) >= 10])
        return title, text, chunks

    section = "Introduction"
    parts: list[str] = []
    article_elements = content.find_all(["h1", "h2", "h3", "h4", "p", "li"])
    for element in article_elements:
        if element.name in {"h1", "h2", "h3", "h4"}:
            if parts:
                chunks.append({"section": section, "text": normalise(" ".join(parts))})
                parts = []
            heading = normalise(element.get_text(" ", strip=True))
            if heading and heading.lower() != title.lower():
                section = heading
        else:
            text = normalise(element.get_text(" ", strip=True))
            if text:
                parts.append(text)
    if parts:
        chunks.append({"section": section, "text": normalise(" ".join(parts))})

    sections = merge_short_sections([chunk for chunk in chunks if len(chunk["text"].split()) >= 10])
    chunks = []
    for section in sections:
        for part in split_words(section["text"]):
            chunks.append({"section": section["section"], "text": normalise(part)})
    chunks = merge_chunks_under_40([chunk for chunk in chunks if len(chunk["text"].split()) >= 10])
    return title, content.get_text("\n", strip=True), chunks


def fetch_articles() -> tuple[list[dict], list[str]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(URL_CSV.open("r", encoding="utf-8")))
    allowlist = {row["url"] for row in rows}
    check_robots([row["url"] for row in rows])
    records: list[dict] = []
    failures: list[str] = []
    options = Options()
    options.binary_location = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(
        "--user-agent=SuperloopInternalHelpAgent/0.1 (portfolio project; polite public-article research)"
    )
    driver = webdriver.Edge(options=options)

    try:
        for index, row in enumerate(rows):
            url = row["url"]
            if url not in allowlist:
                continue
            driver.get(url)
            try:
                WebDriverWait(driver, 20).until(
                    lambda browser: len(browser.find_element("tag name", "body").text) >= 500
                )
                time.sleep(DELAY_SECONDS)
            except Exception as exc:
                failures.append(f"{url}: browser load failed: {type(exc).__name__}")
                continue

            html = driver.page_source
            raw_path = RAW_DIR / f"{index:03d}.html"
            raw_path.write_text(html, encoding="utf-8")
            records.extend(article_records(index, row, html))
            if index < len(rows) - 1:
                time.sleep(DELAY_SECONDS)
    finally:
        driver.quit()

    write_chunks(records)
    return records, failures


def article_records(index: int, row: dict, html: str) -> list[dict]:
    title, _, sections = clean_article(html, row["url"])
    return [
        {
            "id": f"{index:03d}-{chunk_index:03d}",
            "title": title,
            "url": row["url"],
            "category": row["category"],
            "section": chunk["section"],
            "text": chunk["text"],
        }
        for chunk_index, chunk in enumerate(sections)
    ]


def build_from_raw() -> list[dict]:
    """Re-clean and re-chunk the saved raw HTML without fetching anything."""
    rows = list(csv.DictReader(URL_CSV.open("r", encoding="utf-8")))
    records: list[dict] = []
    for index, row in enumerate(rows):
        path = RAW_DIR / f"{index:03d}.html"
        if path.exists():
            records.extend(article_records(index, row, path.read_text(encoding="utf-8")))
    return records


def write_chunks(records: list[dict]) -> None:
    CHUNK_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHUNK_FILE.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    (ROOT / "data" / "cleaned.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "title": record["title"],
                    "url": record["url"],
                    "category": record["category"],
                    "section": record["section"],
                    "text": record["text"],
                },
                ensure_ascii=False,
            )
            + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Fetch, clean and chunk the allow-listed help articles.")
    cli.add_argument("--from-raw", action="store_true", help="re-chunk saved HTML in data/raw without fetching")
    options = cli.parse_args()
    if options.from_raw:
        chunks = build_from_raw()
        write_chunks(chunks)
        print(f"CHUNKS={len(chunks)}")
    else:
        chunks, failed = fetch_articles()
        print(f"CHUNKS={len(chunks)}")
        print(f"FAILURES={len(failed)}")
        for failure in failed:
            print(failure)
