"""Time the final agent code two ways on the same 30 questions, back to back:
1. one MCP stdio session kept open for all questions (persistent)
2. a new MCP stdio session started and closed for every question (per question)

No judge calls. Writes eval/results/final_latency_compare.json.

Usage:
    python scripts/latency_compare.py
"""
import asyncio
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent import PersistentMCPAgent, answer  # noqa: E402


async def main() -> None:
    rows = list(csv.DictReader((ROOT / "eval" / "questions.csv").open("r", encoding="utf-8")))
    questions = [row["question"] for row in rows]

    persistent = []
    async with PersistentMCPAgent() as agent:
        for question in questions:
            loop = asyncio.get_running_loop()
            started = loop.time()
            await agent.answer(question)
            persistent.append(round((loop.time() - started) * 1000))

    per_question = []
    for question in questions:
        # answer() starts the MCP server, but its latency_ms excludes start-up,
        # so time the whole call from outside.
        loop = asyncio.get_running_loop()
        started = loop.time()
        await answer(question)
        per_question.append(round((loop.time() - started) * 1000))

    output = {
        "questions": len(questions),
        "note": "Same final code and questions, run back to back on one machine. "
                "Per-question timings include MCP server start-up and shutdown.",
        "persistent_session": {"median_ms": statistics.median(persistent), "mean_ms": statistics.mean(persistent),
                               "latencies_ms": persistent},
        "session_per_question": {"median_ms": statistics.median(per_question),
                                 "mean_ms": statistics.mean(per_question), "latencies_ms": per_question},
    }
    path = ROOT / "eval" / "results" / "final_latency_compare.json"
    path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({k: v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "latencies_ms"}
                      for k, v in output.items()}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
