from app.ingest import Chunk, chunk_pages


def test_table_page_splits_into_row_chunks_with_header():
    page_text = (
        "Fee | Amount | Frequency\n"
        "Tuition | 45000 | per semester\n"
        "Hostel | 12000 | per semester\n"
        "Library | 2000 | per year\n"
    )
    chunks = chunk_pages([(1, page_text)], target_chars=2000)
    assert len(chunks) == 3, f"expected 3 row chunks, got {len(chunks)}"
    assert all(c.page == 1 for c in chunks)
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[2].chunk_index == 2
    assert "Tuition" in chunks[0].text and "45000" in chunks[0].text
    assert "Hostel" in chunks[1].text and "12000" in chunks[1].text
    assert "Library" in chunks[2].text and "2000" in chunks[2].text
    # Header repeated on every row
    assert all("Fee" in c.text and "Amount" in c.text for c in chunks)


def test_prose_page_unchanged_by_table_detection():
    page_text = "Graduation requires 120 credits minimum. Attendance is 75 percent."
    chunks = chunk_pages([(1, page_text)], target_chars=2000)
    assert len(chunks) == 1
    assert chunks[0].text == page_text


def test_tabular_line_with_single_space_is_not_table():
    page_text = "Fee Amount Frequency\nTuition 45000 per semester"
    chunks = chunk_pages([(1, page_text)], target_chars=2000)
    # Not table-like (single spaces) -> sentence chunker, single chunk
    assert len(chunks) == 1
    assert "Fee Amount Frequency" in chunks[0].text
