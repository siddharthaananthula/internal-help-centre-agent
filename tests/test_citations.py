URL_A = "https://support.superloop.com/support-hub-article/a"
URL_B = "https://support.superloop.com/support-hub-article/b"


def test_unknown_chunk_ids_are_dropped():
    from agent import parse_structured_answer

    raw = '{"answer": "Pay by card.", "chunk_ids": ["000-000", "999-999"]}'
    text, used = parse_structured_answer(raw, {"000-000": URL_A})
    assert text == "Pay by card."
    assert used == ["000-000"]


def test_model_written_urls_are_replaced_by_retrieved_citations():
    from agent import add_chunk_citations

    text = add_chunk_citations("See https://support.superloop.com/support-hub-article/made-up", ["c1", "c2"],
                               {"c1": URL_A, "c2": URL_B})
    assert "made-up" not in text
    assert text.endswith(f"Sources:\n{URL_A}\n{URL_B}")


def test_citation_extraction_has_no_trailing_punctuation():
    from evaluate import extract_citations

    assert extract_citations(f"Sources: {URL_A}, {URL_B}") == [URL_A, URL_B]
