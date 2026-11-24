def test_chunker_preserves_title_text_and_section():
    from ingest import clean_article

    html = """
    <html><head><title>Test article</title></head><body>
    <lightning-formatted-rich-text>
      <h2>Setup</h2><p>Connect the modem to the wall socket and power it on.</p>
    </lightning-formatted-rich-text>
    </body></html>
    """
    title, _, chunks = clean_article(html, "https://support.superloop.com/support-hub-article/test")
    assert title
    assert chunks
    assert "modem" in chunks[0]["text"].lower()
    assert all(set(chunk) == {"section", "text"} for chunk in chunks)


def test_chunker_splits_on_headings():
    from ingest import clean_article

    body = " ".join(["word"] * 160)
    html = f"""
    <html><body><main><h1>Title</h1>
    <h2>Billing</h2><p>Billing {body}</p>
    <h2>Outages</h2><p>Outages {body}</p>
    </main></body></html>
    """
    _, _, chunks = clean_article(html, "https://support.superloop.com/support-hub-article/test")
    assert [chunk["section"] for chunk in chunks] == ["Billing", "Outages"]


def test_robots_check_blocks_disallowed_paths():
    from ingest import disallowed_urls

    robots = "User-agent: *\nDisallow: /private/\n"
    urls = [
        "https://support.superloop.com/support-hub-article/Outage",
        "https://support.superloop.com/private/page",
    ]
    assert disallowed_urls(robots, urls) == ["https://support.superloop.com/private/page"]
