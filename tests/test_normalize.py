from app.normalize import content_hash, normalize_text, split_sections


def test_normalize_collapses_whitespace():
    raw = "  Line one  \n\n\n  Line two  \r\n"
    assert normalize_text(raw) == "Line one\nLine two"


def test_content_hash_stable():
    text = "SEC. 1. Example.\nSEC. 2. More."
    assert content_hash(text) == content_hash(text)
    # Hashing is based on normalized text, so insignificant trailing whitespace should not change it.
    assert content_hash(text) == content_hash(text + " ")


def test_split_sections():
    text = "Preamble\nSEC. 101. First.\nSEC. 102. Second."
    sections = split_sections(text)
    assert len(sections) == 2
    assert sections[0][0].startswith("SEC")
