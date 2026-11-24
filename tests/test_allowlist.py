import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_allowlist_refuses_external_url():
    from mcp_server import get_article

    result = get_article("https://example.com/article")
    assert result["refused"] is True
    assert "allow-list" in result["reason"]


def test_allowlist_refuses_lookalike_superloop_url():
    from mcp_server import get_article

    assert get_article("https://support.superloop.com/support-hub-article/not-on-the-list")["refused"] is True


def test_allowlist_contains_csv_urls():
    from mcp_server import ALLOWLIST

    rows = list(csv.DictReader((ROOT / "eval" / "article_urls.csv").open("r", encoding="utf-8")))
    assert len(rows) == 38
    assert ALLOWLIST == {row["url"] for row in rows}
