from __future__ import annotations

import csv
import os
import sys
from functools import lru_cache
from pathlib import Path

import ssl_bootstrap  # noqa: F401
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP
from retrieval import Retriever

load_dotenv(ROOT / ".env", override=True)

MAX_K = 10

ALLOWLIST = {
    row["url"]
    for row in csv.DictReader((ROOT / "eval" / "article_urls.csv").open("r", encoding="utf-8"))
}
# Clearly fake records for the least-privilege demo. Not real customers.
SYNTHETIC_ACCOUNTS = {
    "ACC-1001": {"status": "Active", "plan": "Home Broadband 250 Mbps", "note": "Synthetic demo record"},
    "ACC-1002": {"status": "Active", "plan": "Home Broadband 1000 Mbps", "note": "Synthetic demo record"},
}

server = FastMCP("Superloop Internal Help Agent")


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()


@server.tool()
def search_help(query: str, k: int = 5) -> list[dict]:
    """Search the allow-listed public Superloop help articles using hybrid retrieval."""
    k = max(1, min(int(k), MAX_K))
    results = get_retriever().hybrid_search(query, k=k)
    return [
        {
            "chunk_id": result["id"],
            "title": result["title"],
            "url": result["url"],
            "section": result["section"],
            "score": result["score"],
            "text": result["text"],
        }
        for result in results
    ]


@server.tool()
def get_article(url: str) -> dict:
    """Read a cleaned article only when its URL is in the allow-list."""
    if url not in ALLOWLIST:
        return {"refused": True, "reason": "URL is not on the allow-list"}
    chunks = [chunk for chunk in get_retriever().chunks if chunk["url"] == url]
    if not chunks:
        return {"refused": True, "reason": "Article is not available locally"}
    return {
        "title": chunks[0]["title"],
        "url": url,
        "text": "\n\n".join(
            f"{chunk['section']}\n{chunk['text']}" for chunk in chunks
        ),
    }


@server.tool()
def lookup_service_status(account_id: str) -> dict:
    """Look up a synthetic account status. Only the caller's verified account can be read."""
    # The verified ID is NOT a tool parameter, so the model cannot supply it.
    # It is set by the host process that launches this server (environment
    # variable VERIFIED_ACCOUNT_ID). The Streamlit demo and the eval set none,
    # so every lookup is refused unless an operator sets it deliberately.
    verified_account_id = os.environ.get("VERIFIED_ACCOUNT_ID", "").strip()
    if not verified_account_id:
        return {"refused": True, "reason": "No verified account session"}
    if account_id != verified_account_id:
        return {"refused": True, "reason": "Account ID verification failed"}
    record = SYNTHETIC_ACCOUNTS.get(account_id)
    if not record:
        return {"refused": True, "reason": "Synthetic account not found"}
    return {"account_id": account_id, **record}


if __name__ == "__main__":
    server.run(transport="stdio")
