from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "assets" / "sdd.css").read_text(encoding="utf-8")


def test_pack_and_checked_in_stylesheets_are_byte_identical() -> None:
    assert (ROOT / "assets" / "sdd.css").read_bytes() == (
        ROOT / "docs" / "sdd" / "assets" / "sdd.css"
    ).read_bytes()


def test_css_exposes_shared_document_hooks() -> None:
    hooks = {
        "skip-link",
        "document-header",
        "document-kind",
        "document-layout",
        "document-outline",
        "metadata",
        "decision-article",
        "term-entry",
        "avoid-terms",
        "plan-task",
        "task-number",
        "task-rail",
    }
    assert all(f".{hook}" in CSS for hook in hooks)


def test_css_uses_relative_reading_tokens_and_local_overflow() -> None:
    assert "--measure: 68ch" in CSS
    assert "grid-template-columns: minmax(0, var(--outline-size)) minmax(0, var(--measure))" in CSS
    assert "@media (max-width: 59.999rem)" in CSS
    assert "position: static" in CSS
    assert "table" in CSS and "overflow-x: auto" in CSS
    assert "pre" in CSS and "overflow: auto" in CSS
    assert "overflow-x: hidden" in CSS
    assert "font-family: ui-sans-serif, system-ui, sans-serif" in CSS
    assert "font-family: ui-monospace, Menlo, monospace" in CSS


def test_css_covers_theme_focus_and_motion_preferences_without_forbidden_visuals() -> None:
    assert "@media (prefers-color-scheme: dark)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert ":focus-visible" in CSS
    assert "outline: 3px solid var(--focus)" in CSS
    assert "background-image" not in CSS
    assert "gradient" not in CSS
    assert "@import" not in CSS
    assert "url(" not in CSS
