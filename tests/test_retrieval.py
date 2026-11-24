import numpy as np

CHUNKS = [
    {"id": "000-000", "title": "Payment plans", "url": "https://support.superloop.com/support-hub-article/a",
     "section": "Instalments", "text": "You can set up a payment plan to pay your bill in instalments."},
    {"id": "001-000", "title": "Outages", "url": "https://support.superloop.com/support-hub-article/b",
     "section": "Check", "text": "Check the nbn network status page for outages in your area."},
]
# BM25 IDF is zero for a term in half the corpus, so pad with unrelated chunks.
CHUNKS += [
    {"id": f"9{i:02d}-000", "title": "Modem lights", "url": f"https://support.superloop.com/support-hub-article/z{i}",
     "section": "Lights", "text": "A solid green light means the modem is powered on."}
    for i in range(4)
]
EMPTY = np.zeros((len(CHUNKS), 3), dtype=np.float32)


def test_bm25_returns_chunks_with_urls_and_ranks_relevant_first():
    from retrieval import Retriever

    retriever = Retriever(chunks=CHUNKS, embeddings=EMPTY)
    results = retriever.bm25_search("outage in my area", k=2)
    assert results[0]["url"].endswith("/b")
    assert all(r["url"].startswith("https://support.superloop.com/") for r in results)
    assert all({"title", "section", "score"} <= set(r) for r in results)


def test_retriever_needs_no_api_key_for_bm25(monkeypatch):
    from retrieval import Retriever

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    retriever = Retriever(chunks=CHUNKS, embeddings=EMPTY)
    assert retriever.bm25_search("payment plan", k=1)[0]["id"] == "000-000"
