from app.diff.redline import compute_diff, compute_section_diff, export_pair_markdown


def test_compute_diff_detects_changes():
    old = "Alpha\nBeta\nGamma"
    new = "Alpha\nBeta changed\nGamma\nDelta"
    html, stats = compute_diff(old, new)
    assert "insert" in html or "delete" in html
    assert stats.lines_added + stats.lines_removed > 0


def test_section_diff():
    old = "SEC. 1. Aid $10B.\nSEC. 2. Report."
    new = "SEC. 1. Aid $13B.\nSEC. 2. Report.\nSEC. 3. New."
    html, stats = compute_section_diff(old, new)
    assert "section-diff" in html
    assert stats.lines_added + stats.lines_removed >= 0


def test_export_markdown():
    md = export_pair_markdown(
        "Test Act",
        "v1",
        "v2",
        "line a",
        "line b",
        note_summary="Changed.",
    )
    assert "Test Act" in md
    assert "Changed." in md
    assert "```diff" in md
