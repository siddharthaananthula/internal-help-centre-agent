"""Write a 10-question sample from a results file to eval/hand_check.csv for manual grading.

Usage:
    python scripts/create_hand_check.py eval/results/final_run1.json
"""
import csv
import json
import random
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "eval" / "results" / "final_run1.json"
results = json.loads(source.read_text(encoding="utf-8"))
random.seed(2026)
sample = random.sample(results["records"], 10)

with (root / "eval" / "hand_check.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["id", "question", "agent_answer", "cited_url", "judge_score", "my_score", "my_notes"])
    for record in sample:
        citations = re.findall(r"https://support\.superloop\.com/[^\s)\],]+", record["answer"])
        writer.writerow([
            record["id"],
            record["question"],
            record["answer"],
            " | ".join(citations),
            record["answer_score"],
            "",
            "",
        ])

print(f"HAND_CHECK_ROWS=10 from {source.name}")
