from app.ingest import Chunk, chunk_pages


def test_chunks_never_cross_page_boundary():
    pages = [(1, "Sentence one. Sentence two. " * 200), (2, "Page two only.")]
    chunks = chunk_pages(pages, target_chars=500)
    assert all(c.page in (1, 2) for c in chunks)
    # No chunk should contain text from both pages
    assert all("Page two only." not in c.text for c in chunks if c.page == 1)
    assert all("Sentence one." not in c.text for c in chunks if c.page == 2)


def test_chunks_split_on_sentence_boundaries():
    pages = [(1, "First sentence. Second sentence. Third sentence. Fourth sentence.")]
    chunks = chunk_pages(pages, target_chars=30)
    # Each chunk ends with a period or is the final chunk
    for c in chunks[:-1]:
        assert c.text.rstrip().endswith(".")
    assert chunks  # at least one chunk produced


def test_chunk_index_resets_per_page():
    pages = [(1, "A. " * 100), (2, "B. " * 100)]
    chunks = chunk_pages(pages, target_chars=200)
    page_1_indices = [c.chunk_index for c in chunks if c.page == 1]
    page_2_indices = [c.chunk_index for c in chunks if c.page == 2]
    assert page_1_indices == list(range(len(page_1_indices)))
    assert page_2_indices == list(range(len(page_2_indices)))


def test_short_page_produces_single_chunk():
    pages = [(1, "Short text.")]
    chunks = chunk_pages(pages, target_chars=2000)
    assert len(chunks) == 1
    assert chunks[0].text == "Short text."
    assert chunks[0].page == 1
    assert chunks[0].chunk_index == 0