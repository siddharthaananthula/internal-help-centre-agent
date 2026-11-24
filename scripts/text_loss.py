import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ingest import clean_article

root = Path(__file__).resolve().parents[1]
rows = list(csv.DictReader((root / "eval" / "article_urls.csv").open("r", encoding="utf-8")))
chunks = [
    json.loads(line)
    for line in (root / "data" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]

print("ARTICLE TEXT-LOSS REPORT")
for index, row in enumerate(rows):
    path = root / "data" / "raw" / f"{index:03d}.html"
    if not path.exists():
        print(row["url"] + " | raw page missing")
        continue
    _, cleaned, _ = clean_article(path.read_text(encoding="utf-8"), row["url"])
    article_chunks = [chunk for chunk in chunks if chunk["url"] == row["url"]]
    cleaned_words = re.findall(r"[A-Za-z0-9']+", cleaned.lower())
    chunk_words = []
    for chunk in article_chunks:
        chunk_words.extend(re.findall(r"[A-Za-z0-9']+", chunk["text"].lower()))

    cleaned_set = set(cleaned_words)
    chunk_set = set(chunk_words)
    if cleaned_set:
        covered = len(cleaned_set & chunk_set)
        loss_pct = (len(cleaned_set) - covered) / len(cleaned_set) * 100
    else:
        loss_pct = 100.0
    print(
        f"{row['url']} | cleaned_words={len(cleaned_words)} "
        f"| chunk_words_before_overlap_dedup={len(chunk_words)} "
        f"| loss_estimate_pct={loss_pct:.2f}"
    )
