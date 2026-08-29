from pathlib import Path
import shutil
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RENDER = SCRIPTS / "render-docs"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _run(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RENDER), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )


def test_render_glossary_keeps_terms_and_does_not_touch_source(tmp_path: Path) -> None:
    src = tmp_path / "CONTEXT.md"
    shutil.copy(FIXTURES / "glossary" / "CONTEXT.md", src)
    before = src.read_bytes()
    result = _run(tmp_path, ["CONTEXT.md"])
    assert result.returncode == 0, result.stderr
    html = (tmp_path / "CONTEXT.html").read_text()
    assert "Order" in html
    assert "Purchase" in html
    assert "<h1" in html
    assert src.read_bytes() == before
    css = tmp_path / "docs" / "sdd" / "assets" / "sdd.css"
    assert css.is_file()
    assert 'href="docs/sdd/assets/sdd.css"' in html


def test_render_is_idempotent(tmp_path: Path) -> None:
    shutil.copy(FIXTURES / "glossary" / "CONTEXT.md", tmp_path / "CONTEXT.md")
    assert _run(tmp_path, ["CONTEXT.md"]).returncode == 0
    first = (tmp_path / "CONTEXT.html").read_bytes()
    assert _run(tmp_path, ["CONTEXT.md"]).returncode == 0
    assert (tmp_path / "CONTEXT.html").read_bytes() == first
    assert "datetime" not in first.decode().lower()


def test_render_defaults_and_relative_css(tmp_path: Path) -> None:
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "plans").mkdir(parents=True)
    shutil.copy(FIXTURES / "glossary" / "CONTEXT.md", tmp_path / "CONTEXT.md")
    shutil.copy(FIXTURES / "adr" / "0001-use-postgres.md", tmp_path / "docs" / "adr" / "0001-use-postgres.md")
    shutil.copy(
        FIXTURES / "spec" / "2026-01-01-example-design.md",
        tmp_path / "docs" / "sdd" / "specs" / "2026-01-01-example-design.md",
    )
    shutil.copy(
        FIXTURES / "plan" / "2026-01-01-example.md",
        tmp_path / "docs" / "sdd" / "plans" / "2026-01-01-example.md",
    )
    result = _run(tmp_path, [])
    assert result.returncode == 0, result.stderr
    adr_html = (tmp_path / "docs" / "adr" / "0001-use-postgres.html").read_text()
    spec_html = (tmp_path / "docs" / "sdd" / "specs" / "2026-01-01-example-design.html").read_text()
    plan_html = (tmp_path / "docs" / "sdd" / "plans" / "2026-01-01-example.html").read_text()
    assert "Postgres" in adr_html
    assert 'href="../sdd/assets/sdd.css"' in adr_html
    assert "Keep Markdown canonical" in spec_html
    assert 'href="../assets/sdd.css"' in spec_html
    assert "UNIQUE_TASK_ONE" in plan_html
    assert 'href="../assets/sdd.css"' in plan_html


def test_missing_explicit_path_is_nonzero(tmp_path: Path) -> None:
    result = _run(tmp_path, ["nope.md"])
    assert result.returncode != 0
    assert "nope.md" in result.stderr


def test_title_special_chars_are_html_escaped(tmp_path: Path) -> None:
    md = tmp_path / "CONTEXT.md"
    md.write_text("# A & B </title>\n\nbody\n", encoding="utf-8")
    result = _run(tmp_path, ["CONTEXT.md"])
    assert result.returncode == 0, result.stderr
    out = (tmp_path / "CONTEXT.html").read_text(encoding="utf-8")
    assert "<title>A &amp; B &lt;/title&gt;</title>" in out
    assert "<title>A & B </title>" not in out


def test_refuses_html_input_without_overwriting(tmp_path: Path) -> None:
    html = tmp_path / "CONTEXT.html"
    html.write_text("<html>keep-me</html>", encoding="utf-8")
    result = _run(tmp_path, ["CONTEXT.html"])
    assert result.returncode != 0
    assert html.read_text(encoding="utf-8") == "<html>keep-me</html>"


def test_refuses_non_markdown_extension(tmp_path: Path) -> None:
    txt = tmp_path / "notes.txt"
    txt.write_text("# Hi\n", encoding="utf-8")
    result = _run(tmp_path, ["notes.txt"])
    assert result.returncode != 0
    assert not (tmp_path / "notes.html").exists()
    assert txt.read_text(encoding="utf-8") == "# Hi\n"


def test_raw_html_is_escaped_and_csp_is_present(tmp_path: Path) -> None:
    md = tmp_path / "CONTEXT.md"
    md.write_text("# Title\n\n<script>alert(1)</script>\n", encoding="utf-8")
    result = _run(tmp_path, ["CONTEXT.md"])
    assert result.returncode == 0, result.stderr
    out = (tmp_path / "CONTEXT.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    assert "Content-Security-Policy" in out


def test_markdown_links_become_anchors(tmp_path: Path) -> None:
    md = tmp_path / "CONTEXT.md"
    md.write_text("# Title\n\nSee [docs](https://example.com/path).\n", encoding="utf-8")
    result = _run(tmp_path, ["CONTEXT.md"])
    assert result.returncode == 0, result.stderr
    out = (tmp_path / "CONTEXT.html").read_text(encoding="utf-8")
    assert '<a href="https://example.com/path">' in out
    assert "docs</a>" in out


def test_fixture_html_matches_goldens(tmp_path: Path) -> None:
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "plans").mkdir(parents=True)
    shutil.copy(FIXTURES / "glossary" / "CONTEXT.md", tmp_path / "CONTEXT.md")
    shutil.copy(FIXTURES / "adr" / "0001-use-postgres.md", tmp_path / "docs" / "adr" / "0001-use-postgres.md")
    shutil.copy(
        FIXTURES / "spec" / "2026-01-01-example-design.md",
        tmp_path / "docs" / "sdd" / "specs" / "2026-01-01-example-design.md",
    )
    shutil.copy(
        FIXTURES / "plan" / "2026-01-01-example.md",
        tmp_path / "docs" / "sdd" / "plans" / "2026-01-01-example.md",
    )
    result = _run(tmp_path, [])
    assert result.returncode == 0, result.stderr
    pairs = (
        (tmp_path / "CONTEXT.html", FIXTURES / "glossary" / "CONTEXT.html"),
        (tmp_path / "docs" / "adr" / "0001-use-postgres.html", FIXTURES / "adr" / "0001-use-postgres.html"),
        (
            tmp_path / "docs" / "sdd" / "specs" / "2026-01-01-example-design.html",
            FIXTURES / "spec" / "2026-01-01-example-design.html",
        ),
        (
            tmp_path / "docs" / "sdd" / "plans" / "2026-01-01-example.html",
            FIXTURES / "plan" / "2026-01-01-example.html",
        ),
    )
    for actual, golden in pairs:
        assert actual.read_text(encoding="utf-8") == golden.read_text(encoding="utf-8")
